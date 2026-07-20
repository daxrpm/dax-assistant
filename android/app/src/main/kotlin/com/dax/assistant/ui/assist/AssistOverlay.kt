package com.dax.assistant.ui.assist

import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.core.tween
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.animation.slideInVertically
import androidx.compose.animation.slideOutVertically
import androidx.compose.foundation.background
import androidx.compose.foundation.interaction.MutableInteractionSource
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Close
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.tooling.preview.Preview
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.dax.assistant.R
import com.dax.assistant.assistant.AgentActivity
import com.dax.assistant.assistant.AssistantState
import com.dax.assistant.audio.AudioRoute
import com.dax.assistant.ui.assistant.VoiceOrb
import com.dax.assistant.ui.design.Orbita
import com.dax.assistant.ui.design.OrbitaTheme
import com.dax.assistant.ui.design.OrbitaType
import com.dax.assistant.ui.design.rememberReduceMotion
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow

/**
 * The surface the system assist gesture puts on screen.
 *
 * It is a bottom sheet rather than a full-screen takeover, and that is the whole
 * design. The gesture fires from a locked phone, from inside another app, often
 * from a pocket; covering what the user was doing to show a microphone would be
 * hostile. Everything above the panel stays visible and dismisses the overlay
 * when touched, so the cost of an accidental trigger is one tap.
 *
 * The panel shows the same orb the in-app assistant screen uses, because a user
 * should not have to learn two vocabularies for the same machine state.
 */
@Composable
fun AssistOverlay(
    state: StateFlow<AssistantState>,
    inputLevel: StateFlow<Float>,
    showCount: StateFlow<Int>,
    onDismiss: () -> Unit,
) {
    val current by state.collectAsStateWithLifecycle()
    val reduceMotion = rememberReduceMotion()

    // The system reuses one session across successive gestures, and the
    // composition survives a hide. Everything below is therefore keyed on the
    // invocation: without it the second gesture would open with `wasActive`
    // still true and dismiss itself before the microphone opened.
    val epoch by showCount.collectAsStateWithLifecycle()

    // Enter on the first frame so the panel slides in rather than appearing.
    var entered by remember(epoch) { mutableStateOf(false) }
    LaunchedEffect(epoch) { entered = true }

    // Close once the turn is genuinely over. Tracking that it started first
    // matters: the overlay opens while the controller is still Idle, and
    // closing on Idle alone would shut it before the microphone ever opened.
    var wasActive by remember(epoch) { mutableStateOf(false) }
    LaunchedEffect(current, epoch) {
        if (current !is AssistantState.Idle) wasActive = true
        if (wasActive && current is AssistantState.Idle) {
            delay(600)
            onDismiss()
        }
    }

    OrbitaTheme {
        Box(Modifier.fillMaxSize()) {
            // Tap anywhere above the panel to dismiss. No ripple: this is a
            // dismissal region, not a button.
            Box(
                Modifier.fillMaxSize().clickable(
                    interactionSource = remember { MutableInteractionSource() },
                    indication = null,
                    role = Role.Button,
                    onClick = onDismiss,
                ),
            )

            AnimatedVisibility(
                visible = entered,
                enter = slideInVertically(tween(Orbita.motion.normalMillis)) { it } +
                    fadeIn(tween(Orbita.motion.normalMillis)),
                exit = slideOutVertically(tween(Orbita.motion.fastMillis)) { it } +
                    fadeOut(tween(Orbita.motion.fastMillis)),
                modifier = Modifier.align(Alignment.BottomCenter),
            ) {
                AssistPanel(current, inputLevel, reduceMotion, onDismiss)
            }
        }
    }
}

@Composable
private fun AssistPanel(
    state: AssistantState,
    inputLevel: StateFlow<Float>,
    reduceMotion: Boolean,
    onDismiss: () -> Unit,
    modifier: Modifier = Modifier,
) {
    Column(
        modifier.fillMaxWidth().widthIn(max = 640.dp)
            .clip(
                RoundedCornerShape(
                    topStart = Orbita.radii.xxl,
                    topEnd = Orbita.radii.xxl,
                ),
            )
            .background(Orbita.colors.bgPanel)
            .navigationBarsPadding()
            .padding(horizontal = Orbita.spacing.edge, vertical = Orbita.spacing.x5),
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        // Grabber. The one affordance that says "this is a sheet" without a word.
        Box(
            Modifier.width(36.dp).height(4.dp)
                .clip(RoundedCornerShape(Orbita.radii.pill))
                .background(Orbita.colors.bgActive),
        )

        Spacer(Modifier.height(Orbita.spacing.x5))

        Box(contentAlignment = Alignment.Center) {
            VoiceOrb(
                state = state,
                inputLevel = inputLevel,
                compact = true,
                reduceMotion = reduceMotion,
            )
        }

        Spacer(Modifier.height(Orbita.spacing.x4))

        Text(
            statusLabel(state),
            style = OrbitaType.title3,
            color = Orbita.colors.fgPrimary,
            textAlign = TextAlign.Center,
        )

        val detail = detailText(state)
        if (detail.isNotBlank()) {
            Spacer(Modifier.height(Orbita.spacing.x2))
            Text(
                detail,
                style = OrbitaType.transcript,
                color = Orbita.colors.fgSecondary,
                textAlign = TextAlign.Center,
                maxLines = 4,
                modifier = Modifier.fillMaxWidth(),
            )
        }

        Spacer(Modifier.height(Orbita.spacing.x4))

        IconButton(
            onClick = onDismiss,
            modifier = Modifier.size(Orbita.sizing.minTouchTarget)
                .clip(RoundedCornerShape(Orbita.radii.pill))
                .background(Orbita.colors.bgInset),
        ) {
            Icon(
                Icons.Filled.Close,
                stringResource(R.string.assist_dismiss),
                tint = Orbita.colors.fgSecondary,
                modifier = Modifier.size(20.dp),
            )
        }
    }
}

@Composable
private fun statusLabel(state: AssistantState): String = stringResource(
    when (state) {
        is AssistantState.Idle -> R.string.status_ready
        is AssistantState.ConnectingAudio -> R.string.status_connecting_audio
        is AssistantState.Listening -> R.string.status_listening
        is AssistantState.Transcribing -> R.string.status_transcribing
        is AssistantState.Processing -> R.string.status_thinking
        is AssistantState.AwaitingApproval -> R.string.status_needs_approval
        is AssistantState.Speaking -> R.string.status_speaking
        is AssistantState.Disconnected -> R.string.status_disconnected
        is AssistantState.Failed -> R.string.status_failed
    },
)

/**
 * The line under the label: what was heard, what is being done, what is being
 * said. Approvals deliberately show nothing here — the overlay is the wrong
 * place to authorize a destructive tool, so that decision stays in the app
 * where the full arguments are visible.
 */
@Composable
private fun detailText(state: AssistantState): String = when (state) {
    is AssistantState.Listening -> state.partialTranscript
    is AssistantState.Transcribing -> state.partialTranscript
    is AssistantState.Processing -> when (val activity = state.activity) {
        is AgentActivity.RunningTool ->
            stringResource(R.string.chat_using_tool, activity.toolName)
        else -> state.streamedReply.ifBlank { state.transcript }
    }
    is AssistantState.AwaitingApproval -> stringResource(R.string.assist_open_app)
    is AssistantState.Speaking -> state.spokenText.ifBlank { state.fullReply }
    is AssistantState.Disconnected -> state.reason
    else -> ""
}

/* ---------------- previews ---------------- */

@Preview(name = "Assist listening", showBackground = true, widthDp = 412, heightDp = 860)
@Composable
private fun AssistListeningPreview() {
    OrbitaTheme(darkTheme = true) {
        AssistPreviewContent(
            AssistantState.Listening(
                route = AudioRoute.Phone,
                partialTranscript = "¿Cuánto espacio libre le queda al disco?",
                speechDetected = true,
            ),
        )
    }
}

@Preview(name = "Assist thinking", showBackground = true, widthDp = 412, heightDp = 860)
@Composable
private fun AssistThinkingPreview() {
    OrbitaTheme(darkTheme = true) {
        AssistPreviewContent(
            AssistantState.Processing(
                transcript = "¿Cuánto espacio libre le queda al disco?",
                activity = AgentActivity.RunningTool("shell_run", "dax-system"),
            ),
        )
    }
}

@Preview(name = "Assist light", showBackground = true, widthDp = 412, heightDp = 860)
@Composable
private fun AssistLightPreview() {
    OrbitaTheme(darkTheme = false) {
        AssistPreviewContent(AssistantState.Listening(route = AudioRoute.Phone))
    }
}

@Composable
private fun AssistPreviewContent(state: AssistantState) {
    Box(Modifier.fillMaxSize()) {
        AssistPanel(
            state = state,
            inputLevel = MutableStateFlow(0.6f),
            reduceMotion = true,
            onDismiss = {},
            modifier = Modifier.align(Alignment.BottomCenter),
        )
    }
}
