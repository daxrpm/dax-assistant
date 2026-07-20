package com.dax.assistant.ui.assistant

import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.systemBarsPadding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Close
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material3.Icon
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.platform.LocalHapticFeedback
import androidx.compose.ui.hapticfeedback.HapticFeedbackType
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.liveRegion
import androidx.compose.ui.semantics.LiveRegionMode
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import com.dax.assistant.assistant.AgentActivity
import com.dax.assistant.assistant.AssistantError
import com.dax.assistant.assistant.AssistantState
import com.dax.assistant.assistant.Turn
import com.dax.assistant.audio.AudioRouteKind
import com.dax.assistant.ui.design.Orbita
import com.dax.assistant.ui.design.OrbitaType

/**
 * The assistant surface.
 *
 * Voice-first means the orb is the interface and everything else is
 * subordinate: one primary target the size of a thumb, live text above it, and
 * history that stays out of the way until wanted. This is not the desktop
 * command deck reflowed — that layout is built around a pointer and a sidebar,
 * neither of which exists here.
 *
 * The status line is an accessibility live region, so a screen-reader user is
 * told the assistant started listening without having to hunt for it.
 */
@Composable
fun AssistantScreen(
    state: AssistantState,
    history: List<Turn>,
    onTrigger: () -> Unit,
    onCancel: () -> Unit,
    onApprove: (String) -> Unit,
    onOpenSettings: () -> Unit,
    modifier: Modifier = Modifier,
) {
    val haptics = LocalHapticFeedback.current

    Box(
        modifier = modifier
            .fillMaxSize()
            .background(Orbita.colors.bgWindow)
            .systemBarsPadding(),
    ) {
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(horizontal = Orbita.spacing.edge),
            horizontalAlignment = Alignment.CenterHorizontally,
        ) {
            TopBar(state = state, onOpenSettings = onOpenSettings)

            Spacer(Modifier.height(Orbita.spacing.x4))

            // History sits above the orb and shrinks as the live area grows,
            // so the thing currently happening always owns the centre.
            Box(Modifier.weight(1f).fillMaxWidth(), contentAlignment = Alignment.BottomCenter) {
                if (history.isEmpty()) {
                    EmptyState(state)
                } else {
                    History(history)
                }
            }

            LiveText(state)

            Spacer(Modifier.height(Orbita.spacing.x5))

            VoiceOrb(
                state = state,
                modifier = Modifier
                    .clip(CircleShape)
                    .clickable(
                        enabled = state.canStartTurn,
                        role = Role.Button,
                        onClickLabel = if (state is AssistantState.Idle) {
                            "Start listening"
                        } else {
                            "Interrupt and start listening"
                        },
                    ) {
                        haptics.performHapticFeedback(HapticFeedbackType.LongPress)
                        onTrigger()
                    }
                    .semantics {
                        contentDescription = describeForAccessibility(state)
                    },
            )

            Spacer(Modifier.height(Orbita.spacing.x4))

            StatusLine(state)

            Spacer(Modifier.height(Orbita.spacing.x5))

            CancelControl(state = state, onCancel = onCancel)

            Spacer(Modifier.height(Orbita.spacing.x6))
        }

        // The approval sheet is modal on purpose. A gated tool is an
        // authorization decision, and the backend denies it on timeout, so
        // burying it behind other UI would silently turn "didn't notice" into
        // "denied".
        AnimatedVisibility(
            visible = state is AssistantState.AwaitingApproval,
            enter = fadeIn(),
            exit = fadeOut(),
        ) {
            (state as? AssistantState.AwaitingApproval)?.let { pending ->
                ApprovalSheet(request = pending.request, onDecision = onApprove)
            }
        }
    }
}

@Composable
private fun TopBar(state: AssistantState, onOpenSettings: () -> Unit) {
    Row(
        modifier = Modifier.fillMaxWidth().padding(top = Orbita.spacing.x3),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        RouteChip(state)
        Spacer(Modifier.weight(1f))
        Box(
            modifier = Modifier
                .size(Orbita.sizing.minTouchTarget)
                .clip(CircleShape)
                .clickable(role = Role.Button, onClick = onOpenSettings)
                .semantics { contentDescription = "Settings and diagnostics" },
            contentAlignment = Alignment.Center,
        ) {
            Icon(
                imageVector = Icons.Filled.Settings,
                contentDescription = null,
                tint = Orbita.colors.fgTertiary,
                modifier = Modifier.size(22.dp),
            )
        }
    }
}

/** Where audio is going. Shown always, because it changes without warning. */
@Composable
private fun RouteChip(state: AssistantState) {
    val route = when (state) {
        is AssistantState.Listening -> state.route
        is AssistantState.ConnectingAudio -> state.route
        is AssistantState.Speaking -> state.route
        else -> null
    }
    val label = when {
        state is AssistantState.Disconnected -> "Offline"
        route == null -> "Phone"
        route.kind == AudioRouteKind.BLUETOOTH_SCO -> route.productName
        route.kind == AudioRouteKind.WIRED -> "Wired"
        else -> "Phone"
    }
    val tone =
        if (state is AssistantState.Disconnected) Orbita.colors.danger else Orbita.colors.fgTertiary

    Row(verticalAlignment = Alignment.CenterVertically) {
        Box(Modifier.size(6.dp).clip(CircleShape).background(tone))
        Spacer(Modifier.size(Orbita.spacing.x2))
        Text(text = label.uppercase(), style = OrbitaType.label, color = tone)
    }
}

@Composable
private fun EmptyState(state: AssistantState) {
    if (state !is AssistantState.Idle) return
    Column(
        horizontalAlignment = Alignment.CenterHorizontally,
        modifier = Modifier.padding(bottom = Orbita.spacing.x6),
    ) {
        Text(
            text = "Tap to talk to Dax",
            style = OrbitaType.title2,
            color = Orbita.colors.fgSecondary,
        )
        Spacer(Modifier.height(Orbita.spacing.x2))
        Text(
            text = "Or use the assistant gesture, or a headset button.",
            style = OrbitaType.callout,
            color = Orbita.colors.fgQuaternary,
            textAlign = TextAlign.Center,
        )
    }
}

@Composable
private fun History(history: List<Turn>) {
    LazyColumn(
        modifier = Modifier.fillMaxWidth(),
        reverseLayout = true,
        verticalArrangement = Arrangement.spacedBy(Orbita.spacing.x3),
        contentPadding = androidx.compose.foundation.layout.PaddingValues(
            bottom = Orbita.spacing.x4,
        ),
    ) {
        items(history.reversed(), key = { it.id }) { turn ->
            Column(Modifier.fillMaxWidth()) {
                if (turn.userText.isNotBlank()) {
                    Text(
                        text = turn.userText,
                        style = OrbitaType.callout,
                        color = Orbita.colors.fgQuaternary,
                    )
                    Spacer(Modifier.height(Orbita.spacing.x1))
                }
                Text(
                    text = turn.assistantText,
                    style = OrbitaType.conversation,
                    color = Orbita.colors.fgPrimary,
                )
            }
        }
    }
}

/** Live transcription and streamed reply — the text that changes as you speak. */
@Composable
private fun LiveText(state: AssistantState) {
    val text = when (state) {
        is AssistantState.Listening -> state.partialTranscript
        is AssistantState.Transcribing -> state.partialTranscript
        is AssistantState.Processing -> state.transcript
        is AssistantState.AwaitingApproval -> state.transcript
        is AssistantState.Speaking -> state.spokenText
        else -> ""
    }
    Box(
        modifier = Modifier.fillMaxWidth().heightIn(min = 64.dp),
        contentAlignment = Alignment.Center,
    ) {
        if (text.isNotBlank()) {
            Text(
                text = text,
                // Light weight distinguishes in-flight speech from a settled
                // turn without relying on colour.
                style = if (state is AssistantState.Speaking) {
                    OrbitaType.conversation
                } else {
                    OrbitaType.transcript
                },
                color = Orbita.colors.fgPrimary,
                textAlign = TextAlign.Center,
                maxLines = 4,
            )
        }
    }
}

@Composable
private fun StatusLine(state: AssistantState) {
    val (label, tone) = when (state) {
        is AssistantState.Idle -> "" to Orbita.colors.fgTertiary
        is AssistantState.ConnectingAudio -> "Opening the microphone" to Orbita.colors.fgTertiary
        is AssistantState.Listening ->
            (if (state.speechDetected) "Listening" else "Go ahead") to Orbita.colors.accent

        is AssistantState.Transcribing -> "Transcribing" to Orbita.colors.purple
        is AssistantState.Processing -> describeActivity(state.activity) to Orbita.colors.purple
        is AssistantState.AwaitingApproval -> "Needs your approval" to Orbita.colors.warning
        is AssistantState.Speaking -> "Speaking" to Orbita.colors.success
        is AssistantState.Disconnected ->
            (if (state.reconnecting) "Reconnecting…" else state.reason) to Orbita.colors.danger

        is AssistantState.Failed -> describeError(state.error) to Orbita.colors.danger
    }

    Box(
        modifier = Modifier
            .heightIn(min = 24.dp)
            // Announced to screen readers as it changes, so state is not
            // conveyed by the orb's animation alone.
            .semantics { liveRegion = LiveRegionMode.Polite },
        contentAlignment = Alignment.Center,
    ) {
        if (label.isNotBlank()) {
            Text(text = label.uppercase(), style = OrbitaType.label, color = tone)
        }
    }
}

@Composable
private fun CancelControl(state: AssistantState, onCancel: () -> Unit) {
    AnimatedVisibility(visible = state.cancellable, enter = fadeIn(), exit = fadeOut()) {
        Row(
            modifier = Modifier
                .clip(RoundedCornerShape(Orbita.radii.pill))
                .background(Orbita.colors.bgElevated)
                .clickable(role = Role.Button, onClick = onCancel)
                .padding(horizontal = Orbita.spacing.x5, vertical = Orbita.spacing.x3)
                .heightIn(min = 28.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Icon(
                imageVector = Icons.Filled.Close,
                contentDescription = null,
                tint = Orbita.colors.fgSecondary,
                modifier = Modifier.size(16.dp),
            )
            Spacer(Modifier.size(Orbita.spacing.x2))
            Text(text = "Cancel", style = OrbitaType.callout, color = Orbita.colors.fgSecondary)
        }
    }
}

private fun describeActivity(activity: AgentActivity?): String = when (activity) {
    null, AgentActivity.Thinking -> "Thinking"
    is AgentActivity.RunningTool -> "Running ${activity.toolName}"
    is AgentActivity.ToolFinished -> if (activity.ok) "Thinking" else "Tool failed"
}

private fun describeError(error: AssistantError): String = when (error) {
    is AssistantError.Network -> error.detail
    is AssistantError.Authentication -> error.detail
    is AssistantError.Audio -> error.detail
    is AssistantError.Recognition -> error.detail
    is AssistantError.Backend -> error.detail
    AssistantError.PermissionDenied -> "Microphone permission needed"
    AssistantError.Cancelled -> "Cancelled"
}

private fun describeForAccessibility(state: AssistantState): String = when (state) {
    is AssistantState.Idle -> "Start talking to Dax"
    is AssistantState.ConnectingAudio -> "Opening the microphone. Tap to cancel."
    is AssistantState.Listening -> "Listening. Tap to cancel."
    is AssistantState.Transcribing -> "Transcribing. Tap to cancel."
    is AssistantState.Processing -> "Dax is thinking. Tap to cancel."
    is AssistantState.AwaitingApproval -> "Waiting for your approval"
    is AssistantState.Speaking -> "Dax is speaking. Tap to interrupt."
    is AssistantState.Disconnected -> "Not connected to Dax"
    is AssistantState.Failed -> "Something went wrong. Tap to try again."
}
