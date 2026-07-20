package com.dax.assistant.trigger

import android.content.Intent
import android.os.Bundle
import android.service.voice.VoiceInteractionService
import android.service.voice.VoiceInteractionSession
import android.service.voice.VoiceInteractionSessionService
import android.view.View
import androidx.activity.ComponentActivity
import androidx.compose.ui.platform.ComposeView
import androidx.compose.ui.platform.ViewCompositionStrategy
import com.dax.assistant.assistant.AssistantController
import com.dax.assistant.core.log.DaxLog
import com.dax.assistant.service.AssistantService
import com.dax.assistant.ui.assist.AssistOverlay
import com.dax.assistant.ui.assist.SessionOwners
import dagger.hilt.android.AndroidEntryPoint
import javax.inject.Inject
import kotlinx.coroutines.flow.MutableStateFlow

/**
 * Registering as the system assistant.
 *
 * Two things come with the role, and the second one is why it matters more than
 * the assist gesture:
 *
 *  1. Long-press power / swipe-from-corner reaches [DaxVoiceInteractionSession].
 *  2. Android's foreground-service restrictions exempt the app that provides a
 *     `VoiceInteractionService` from the rule that a microphone service cannot
 *     be started from the background. Without the role, a trigger arriving
 *     while the app is not visible cannot legally open the microphone.
 *
 * The role cannot be granted programmatically — `RoleManager` has no request
 * flow for ASSISTANT — so the user selects Dax in Settings. HyperOS has been
 * reported to revert that selection after updates, which is why the app checks
 * rather than assumes it still holds.
 */
class DaxVoiceInteractionService : VoiceInteractionService() {
    override fun onReady() {
        super.onReady()
        DaxLog.i(TAG, "Voice interaction service ready")
    }

    private companion object {
        const val TAG = "DaxVIS"
    }
}

@AndroidEntryPoint
class DaxVoiceInteractionSessionService : VoiceInteractionSessionService() {

    @Inject
    lateinit var controller: AssistantController

    override fun onNewSession(args: Bundle?): VoiceInteractionSession =
        DaxVoiceInteractionSession(this, controller)
}

/**
 * The session the system starts for an assist gesture.
 *
 * It shows a bottom sheet, not a takeover. The gesture fires from a locked
 * phone, from inside another app, sometimes from a pocket, so covering what the
 * user was doing would be hostile — everything above the panel stays visible
 * and dismisses on touch. The turn still runs on [AssistantService], which owns
 * the microphone and the notification; this session only observes and draws.
 *
 * Composition lives between `onShow` and `onHide` via [SessionOwners], so the
 * orb's animations are not running against the battery while nothing is on
 * screen.
 */
class DaxVoiceInteractionSession(
    private val service: DaxVoiceInteractionSessionService,
    private val controller: AssistantController,
) : VoiceInteractionSession(service) {

    private val owners = SessionOwners()
    private var composeView: ComposeView? = null

    /**
     * Counts invocations. The system reuses one session across gestures and the
     * composition outlives a hide, so the overlay keys its per-invocation state
     * on this rather than on first composition.
     */
    private val showCount = MutableStateFlow(0)

    override fun onCreateContentView(): View {
        val view = ComposeView(context).apply {
            setViewCompositionStrategy(ViewCompositionStrategy.DisposeOnDetachedFromWindow)
            setBackgroundColor(android.graphics.Color.TRANSPARENT)
            setContent {
                AssistOverlay(
                    state = controller.state,
                    inputLevel = controller.inputLevel,
                    showCount = showCount,
                    onDismiss = ::dismiss,
                )
            }
        }
        owners.attach(view)
        composeView = view
        return view
    }

    override fun onShow(args: Bundle?, showFlags: Int) {
        super.onShow(args, showFlags)
        DaxLog.i(TAG, "Assist gesture received")
        showCount.value += 1
        owners.show()
        AssistantService.triggerTurn(service, source = "assist-gesture")
    }

    override fun onHide() {
        owners.hide()
        super.onHide()
    }

    override fun onDestroy() {
        owners.destroy()
        composeView = null
        super.onDestroy()
    }

    /**
     * Dismissal cancels an in-flight turn. Leaving the microphone open after
     * the user has visibly closed the surface is exactly the behaviour that
     * makes people distrust an always-listening app.
     */
    private fun dismiss() {
        if (controller.state.value.cancellable) controller.cancel()
        hide()
    }

    private companion object {
        const val TAG = "DaxVISession"
    }
}

/**
 * Catches `android.intent.action.VOICE_COMMAND`.
 *
 * AOSP's `HeadsetSystemInterface.activateVoiceRecognition()` responds to an
 * `AT+BVRA=1` from a Bluetooth headset by starting an activity with this
 * action. It is an ordinary activity intent, so any app can register for it —
 * the assistant role is not required — and because the system starts it, the
 * app is legitimately foreground and may open the microphone.
 *
 * This is the path a headset's assistant button takes. The Redmi Watch 5 Lite
 * has no such control, but earbuds generally do.
 */
class VoiceCommandActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        DaxLog.i(TAG, "VOICE_COMMAND intent received")
        AssistantService.triggerTurn(this, source = "bluetooth-bvra")
        // Nothing to show: the turn runs on the service and the notification
        // carries the state. Finishing immediately keeps the launcher clean.
        finish()
    }

    private companion object {
        const val TAG = "VoiceCommandActivity"
    }
}

/** Entry point for `ACTION_ASSIST` when Dax is not the selected assistant. */
class AssistActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val source = if (intent?.action == Intent.ACTION_ASSIST) "action-assist" else "launcher"
        AssistantService.triggerTurn(this, source = source)
        finish()
    }
}
