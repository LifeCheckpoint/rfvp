//! Headless full-engine preview host for editor embedding (Phase 0 spike).
//!
//! Unlike [`crate::soft_host`], this module owns no windowing: it boots the
//! complete engine (subsystem + script VM + vm_worker + soft_render) directly
//! from an in-memory HCB byte buffer and steps one frame at a time, exposing
//! the resulting RGBA [`SoftFramebuffer`] to the caller. This is the target
//! surface for Electron embedding in Phase 1 (shared-memory transport).
//!
//! The boot and frame loop are intentionally a line-for-line adaptation of
//! [`crate::soft_host::SoftHost`] with the winit / softbuffer presentation
//! layer removed.

use std::sync::{Arc, RwLock, RwLockReadGuard, RwLockWriteGuard};

use anyhow::Result;

use crate::{
    host_api::{PointerButton, RfvpEvent},
    script::{global::GLOBAL, parser::Nls},
    soft_render::{create_soft_renderer, PixelFormat, SoftFramebuffer, SoftRenderer},
    subsystem::{
        anzu_scene::AnzuScene,
        resources::{
            input_manager::KeyCode,
            motion_manager::DissolveType,
            thread_manager::ThreadManager,
            vfs::Vfs,
            window::Window as EngineWindow,
        },
        scene::{SceneAction, SceneMachine},
        scheduler::Scheduler,
        world::GameData,
    },
    vm_worker::VmWorker,
};

#[inline]
fn gd_read(gd: &Arc<RwLock<Box<GameData>>>) -> RwLockReadGuard<'_, Box<GameData>> {
    match gd.read() {
        Ok(g) => g,
        Err(poisoned) => poisoned.into_inner(),
    }
}

#[inline]
fn gd_write(gd: &Arc<RwLock<Box<GameData>>>) -> RwLockWriteGuard<'_, Box<GameData>> {
    match gd.write() {
        Ok(g) => g,
        Err(poisoned) => poisoned.into_inner(),
    }
}

/// Result of one preview frame step.
#[derive(Debug, Clone, Copy, Default)]
pub struct PreviewTick {
    /// Frame delta in milliseconds, as fed to the VM worker.
    pub frame_ms: u64,
    /// Whether the main script thread (context 0) has run to completion.
    pub main_thread_exited: bool,
}

/// A headless host that boots and advances the full engine on the caller's thread.
pub struct PreviewHost {
    title: String,
    game_data: Arc<RwLock<Box<GameData>>>,
    vm_worker: VmWorker,
    scheduler: Scheduler,
    layer_machine: SceneMachine,
    renderer: SoftRenderer,
    virtual_size: (u32, u32),
    last_dissolve_type: DissolveType,
    last_dissolve2_transitioning: bool,
}

impl PreviewHost {
    /// Point the engine VFS at a resource root directory before booting.
    ///
    /// The VFS reads archive packs (`graph_bg.bin`, `graph_bs.bin`, …) from
    /// this directory. Phase 0 tolerates an empty/missing directory; call this
    /// only when real archive files are available.
    pub fn set_resource_root(path: &str) {
        crate::utils::file::set_base_path(path);
    }

    /// Boot the full engine from an in-memory HCB byte buffer.
    ///
    /// `script_entry` overrides the HCB header entry point so the embedded
    /// preview can jump straight into the compiled scene function instead of
    /// running the title/logo launcher flow.
    pub fn boot_from_bytes(bytes: Vec<u8>, nls: Nls, script_entry: u32) -> Result<Self> {
        let parser = crate::script::parser::Parser::from_bytes(bytes, nls)?;
        let title = parser.get_title();
        let virtual_size = parser.get_screen_size();

        let mut world = boxed_default_game_data();
        world.vfs = match Vfs::new(nls) {
            Ok(vfs) => vfs,
            Err(e) => {
                // Phase 0：资源目录可能为空或不存在，VM 仍应能 boot 跑通。
                log::warn!("PreviewHost: Vfs::new failed, using empty VFS: {:#}", e);
                Vfs::default()
            }
        };
        world.nls = parser.nls;
        world.set_can_fullscreen(false);
        world.set_window(EngineWindow::new(virtual_size, 1.0));

        GLOBAL.lock().unwrap().init_with(
            parser.get_non_volatile_global_count(),
            parser.get_volatile_global_count(),
        );

        let mut script_engine = ThreadManager::new();
        // Override the default entry point with the compiled scene entry.
        script_engine.thread_start(0, script_entry);

        let mut layer_machine = SceneMachine {
            current_scene: Some(Box::<AnzuScene>::default()),
        };
        layer_machine.apply_scene_action(SceneAction::Start, &mut world);

        let game_data = Arc::new(RwLock::new(world));
        let vm_worker = VmWorker::spawn(game_data.clone(), parser.clone(), script_engine);

        Ok(Self {
            title,
            game_data,
            vm_worker,
            scheduler: Scheduler::default(),
            layer_machine,
            renderer: create_soft_renderer(
                virtual_size.0.max(1),
                virtual_size.1.max(1),
                PixelFormat::Rgba8,
            )?,
            virtual_size,
            last_dissolve_type: DissolveType::None,
            last_dissolve2_transitioning: false,
        })
    }

    /// HCB 标题（标题栏文本）。
    pub fn title(&self) -> &str {
        &self.title
    }

    /// Advance the engine by one frame and render the resulting RGBA frame.
    pub fn tick(&mut self) -> Result<PreviewTick> {
        let (frame_ms, notify_dissolve_done) = self.next_frame();
        if notify_dissolve_done {
            self.vm_worker.send_dissolve_done_sync();
        }
        let _report = self.vm_worker.send_frame_ms_sync(frame_ms);
        self.finish_frame();

        {
            let mut gd = gd_write(&self.game_data);
            self.layer_machine
                .apply_scene_action(SceneAction::EndFrame, &mut gd);
        }

        let main_thread_exited = {
            let gd = gd_read(&self.game_data);
            self.renderer.render_frame(&gd.motion_manager)?;
            gd.get_main_thread_exited()
        };

        gd_write(&self.game_data).inputs_manager.frame_reset();

        Ok(PreviewTick {
            frame_ms,
            main_thread_exited,
        })
    }

    /// The latest rendered RGBA framebuffer.
    pub fn framebuffer(&self) -> &SoftFramebuffer {
        self.renderer.framebuffer()
    }

    /// Virtual screen width in pixels.
    pub fn width(&self) -> u32 {
        self.virtual_size.0
    }

    /// Virtual screen height in pixels.
    pub fn height(&self) -> u32 {
        self.virtual_size.1
    }

    /// Restart the main script thread at `addr` (label jump for the editor).
    pub fn jump_to(&mut self, addr: u32) {
        {
            let mut gd = gd_write(&self.game_data);
            gd.set_main_thread_exited(false);
            gd.set_lock_scripter(false);
        }
        self.vm_worker.jump_sync(addr);
    }

    /// Inject a host input event into [`GameData::inputs_manager`].
    ///
    /// Phase 0 only implements the pointer subset (down/up/move); keyboard and
    /// touch dispatch are left as a Phase 1 TODO.
    pub fn handle_event(&mut self, event: RfvpEvent) {
        {
            let mut gd = gd_write(&self.game_data);
            match event {
                RfvpEvent::PointerDown { button, x, y } => {
                    gd.inputs_manager.set_mouse_in(true);
                    gd.inputs_manager.notify_mouse_move(x, y);
                    gd.inputs_manager.notify_mouse_down(pointer_keycode(button));
                }
                RfvpEvent::PointerUp { button, x, y } => {
                    gd.inputs_manager.set_mouse_in(true);
                    gd.inputs_manager.notify_mouse_move(x, y);
                    gd.inputs_manager.notify_mouse_up(pointer_keycode(button));
                }
                RfvpEvent::PointerMove { x, y, .. } => {
                    gd.inputs_manager.set_mouse_in(true);
                    gd.inputs_manager.notify_mouse_move(x, y);
                }
                _ => {
                    // TODO(Phase 1): keyboard / touch / wheel / quit dispatch.
                }
            }
        }
        self.vm_worker.send_input_signal();
    }

    fn next_frame(&mut self) -> (u64, bool) {
        let mut notify_dissolve_done = false;
        let frame_ms: u64;

        {
            let mut gd_guard = gd_write(&self.game_data);
            let gd = &mut *gd_guard;
            gd.motion_manager.text_manager.set_render_scale(1.0);

            let frame_duration = gd.time_mut_ref().frame();
            let frame_us = frame_duration.as_micros() as u64;
            frame_ms = if frame_us == 0 {
                0
            } else {
                (frame_us + 999) / 1000
            };
            gd.timer_manager.tick(frame_ms.min(u32::MAX as u64) as u32);
            gd.inputs_manager.begin_frame();

            let mut video_tick_failed = false;
            {
                let (video_manager, motion_manager) =
                    (&mut gd.video_manager, &mut gd.motion_manager);
                if let Err(e) = video_manager.tick(motion_manager) {
                    log::error!("VideoPlayerManager::tick failed: {:?}", e);
                    video_tick_failed = true;
                }
            }
            if video_tick_failed {
                let (video_manager, motion_manager) =
                    (&mut gd.video_manager, &mut gd.motion_manager);
                video_manager.stop(motion_manager);
                gd.set_halt(false);
            }

            let cur_dissolve = gd.motion_manager.get_dissolve_type();
            if (self.last_dissolve_type != DissolveType::None
                && self.last_dissolve_type != DissolveType::Static)
                && (cur_dissolve == DissolveType::None || cur_dissolve == DissolveType::Static)
            {
                notify_dissolve_done = true;
            }

            let cur_dissolve2 = gd.motion_manager.is_dissolve2_transitioning();
            if self.last_dissolve2_transitioning && !cur_dissolve2 {
                notify_dissolve_done = true;
            }
            self.last_dissolve2_transitioning = cur_dissolve2;
            self.last_dissolve_type = cur_dissolve;

            gd.set_current_thread(0);
            if gd.get_halt() {
                gd.set_halt(false);
            }
        }

        (frame_ms, notify_dissolve_done)
    }

    fn finish_frame(&mut self) {
        let mut gd_guard = gd_write(&self.game_data);
        let gd = &mut *gd_guard;

        self.layer_machine
            .apply_scene_action(SceneAction::Update, gd);
        self.scheduler.execute(gd);
        self.layer_machine
            .apply_scene_action(SceneAction::LateUpdate, gd);

        gd.set_current_thread(0);
    }
}

fn pointer_keycode(button: PointerButton) -> KeyCode {
    match button {
        PointerButton::Left => KeyCode::LeftClick,
        PointerButton::Right => KeyCode::RightClick,
        PointerButton::Middle | PointerButton::Other(_) => KeyCode::LeftClick,
    }
}

fn boxed_default_game_data() -> Box<GameData> {
    let mut boxed: Box<std::mem::MaybeUninit<GameData>> = Box::new_uninit();
    unsafe {
        GameData::init_default_in_place(boxed.as_mut_ptr().cast());
        let raw: *mut GameData = Box::into_raw(boxed).cast();
        Box::from_raw(raw)
    }
}
