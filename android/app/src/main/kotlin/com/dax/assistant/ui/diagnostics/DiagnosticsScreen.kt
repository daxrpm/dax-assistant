package com.dax.assistant.ui.diagnostics

import androidx.compose.animation.animateColorAsState
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
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.clearAndSetSemantics
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import com.dax.assistant.diagnostics.CapabilityCheck
import com.dax.assistant.diagnostics.CapabilityReport
import com.dax.assistant.diagnostics.CheckStatus
import com.dax.assistant.diagnostics.DiagnosticsUiState
import com.dax.assistant.ui.design.Orbita
import com.dax.assistant.ui.design.OrbitaType

/**
 * The capability report, rendered.
 *
 * This screen exists to answer one question honestly: can this phone actually
 * run a conversation through the watch? So it leads with the verdict, and the
 * individual checks are the evidence behind it rather than the point.
 *
 * Status is never carried by colour alone — each row has a glyph and the
 * status word is in the accessibility label — because a red/green dot is
 * exactly the thing colour-blind users and screen readers lose.
 */
@Composable
fun DiagnosticsScreen(
    state: DiagnosticsUiState,
    onRunProbe: () -> Unit,
    onRequestPermissions: () -> Unit,
    modifier: Modifier = Modifier,
) {
    Column(
        modifier = modifier
            .fillMaxSize()
            .background(Orbita.colors.bgWindow)
            .systemBarsPadding()
            .verticalScroll(rememberScrollState())
            .padding(horizontal = Orbita.spacing.edge, vertical = Orbita.spacing.x6),
    ) {
        Text(
            text = "Audio diagnostics",
            style = OrbitaType.largeTitle,
            color = Orbita.colors.fgPrimary,
        )
        Spacer(Modifier.height(Orbita.spacing.x2))
        Text(
            text = "Whether a watch or headset can actually carry a conversation. " +
                "Nothing in Dax trusts a paired device until these pass.",
            style = OrbitaType.callout,
            color = Orbita.colors.fgTertiary,
        )

        Spacer(Modifier.height(Orbita.spacing.x6))

        if (!state.permissionsGranted) {
            PermissionPrompt(onRequestPermissions)
            Spacer(Modifier.height(Orbita.spacing.x5))
        }

        VerdictCard(report = state.report, running = state.running)

        Spacer(Modifier.height(Orbita.spacing.x5))

        state.report.checks.forEach { check ->
            CheckRow(check)
            Spacer(Modifier.height(Orbita.spacing.x2))
        }

        Spacer(Modifier.height(Orbita.spacing.x6))

        PrimaryAction(
            label = when {
                state.running -> "Running…"
                state.report.hasRun -> "Run again"
                else -> "Run diagnostics"
            },
            enabled = !state.running && state.permissionsGranted,
            onClick = onRunProbe,
        )

        Spacer(Modifier.height(Orbita.spacing.x4))
        Text(
            text = "Speaker playback confirms the engine finished rendering into " +
                "the voice-call stream. It cannot confirm you heard it — check " +
                "the device itself.",
            style = OrbitaType.footnote,
            color = Orbita.colors.fgQuaternary,
        )
        Spacer(Modifier.height(Orbita.spacing.x8))
    }
}

@Composable
private fun VerdictCard(report: CapabilityReport, running: Boolean) {
    val usable = report.watchAudioUsable
    val tone = when {
        running || !report.hasRun -> Orbita.colors.fgTertiary
        usable -> Orbita.colors.success
        else -> Orbita.colors.warning
    }
    val headline = when {
        running -> "Testing…"
        !report.hasRun -> "Not tested yet"
        usable -> "Bluetooth audio is usable"
        else -> "Falling back to the phone"
    }
    val detail = when {
        running -> "Opening the route and capturing a sample."
        !report.hasRun -> "Dax uses the phone microphone until these checks pass."
        usable -> report.deviceName.ifBlank { "Connected device" } +
            " can capture and play a conversation."
        else -> "Dax stays fully usable — it will use the phone microphone and speaker."
    }

    Column(
        modifier = Modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(Orbita.radii.xl))
            .background(Orbita.colors.bgPanel)
            .padding(Orbita.spacing.x5),
    ) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            if (running) {
                CircularProgressIndicator(
                    modifier = Modifier.size(18.dp),
                    color = Orbita.colors.accent,
                    strokeWidth = 2.dp,
                )
            } else {
                Box(
                    Modifier
                        .size(10.dp)
                        .clip(CircleShape)
                        .background(tone),
                )
            }
            Spacer(Modifier.size(Orbita.spacing.x3))
            Text(text = headline, style = OrbitaType.title2, color = Orbita.colors.fgPrimary)
        }
        Spacer(Modifier.height(Orbita.spacing.x2))
        Text(text = detail, style = OrbitaType.callout, color = Orbita.colors.fgSecondary)

        if (report.hasRun) {
            Spacer(Modifier.height(Orbita.spacing.x3))
            Text(
                text = "${report.passCount} passed · ${report.failCount} failed",
                style = OrbitaType.monoSmall,
                color = Orbita.colors.fgQuaternary,
            )
        }
    }
}

@Composable
private fun CheckRow(check: CapabilityCheck) {
    val statusWord = when (check.status) {
        CheckStatus.PASS -> "Passed"
        CheckStatus.FAIL -> "Failed"
        CheckStatus.SKIPPED -> "Skipped"
        CheckStatus.NOT_RUN -> "Not run"
    }
    val tone by animateColorAsState(
        targetValue = when (check.status) {
            CheckStatus.PASS -> Orbita.colors.success
            CheckStatus.FAIL -> Orbita.colors.danger
            CheckStatus.SKIPPED -> Orbita.colors.warning
            CheckStatus.NOT_RUN -> Orbita.colors.fgQuaternary
        },
        label = "checkTone",
    )

    Row(
        modifier = Modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(Orbita.radii.lg))
            .background(Orbita.colors.bgContent)
            .padding(Orbita.spacing.x4)
            .semantics {
                contentDescription = buildString {
                    append(check.title)
                    append(": ")
                    append(statusWord)
                    if (check.detail.isNotBlank()) {
                        append(". ")
                        append(check.detail)
                    }
                }
            },
        verticalAlignment = Alignment.Top,
    ) {
        // A glyph as well as a colour: status must survive a colour-blind
        // reader and a greyscale screenshot.
        Text(
            text = when (check.status) {
                CheckStatus.PASS -> "✓"
                CheckStatus.FAIL -> "✕"
                CheckStatus.SKIPPED -> "–"
                CheckStatus.NOT_RUN -> "·"
            },
            style = OrbitaType.mono,
            color = tone,
            modifier = Modifier
                .size(20.dp)
                .clearAndSetSemantics { },
            textAlign = TextAlign.Center,
        )
        Spacer(Modifier.size(Orbita.spacing.x3))
        Column(Modifier.weight(1f)) {
            Text(
                text = check.title,
                style = OrbitaType.body,
                color = Orbita.colors.fgPrimary,
            )
            if (check.detail.isNotBlank()) {
                Spacer(Modifier.height(Orbita.spacing.x1))
                // Mono, because this is machine evidence — a device id, a
                // sample rate, an exception. The sans/mono split is the rule.
                Text(
                    text = check.detail,
                    style = OrbitaType.monoSmall,
                    color = Orbita.colors.fgTertiary,
                )
            }
        }
    }
}

@Composable
private fun PermissionPrompt(onRequest: () -> Unit) {
    Column(
        modifier = Modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(Orbita.radii.xl))
            .background(Orbita.colors.accentDim)
            .padding(Orbita.spacing.x5),
    ) {
        Text(
            text = "Microphone and Bluetooth access needed",
            style = OrbitaType.title3,
            color = Orbita.colors.fgPrimary,
        )
        Spacer(Modifier.height(Orbita.spacing.x2))
        Text(
            text = "The probe records about a second of audio to prove capture " +
                "works. It is never sent anywhere and never written to disk.",
            style = OrbitaType.callout,
            color = Orbita.colors.fgSecondary,
        )
        Spacer(Modifier.height(Orbita.spacing.x4))
        PrimaryAction(label = "Grant access", enabled = true, onClick = onRequest)
    }
}

@Composable
private fun PrimaryAction(label: String, enabled: Boolean, onClick: () -> Unit) {
    val background = if (enabled) Orbita.colors.accent else Orbita.colors.bgElevated
    val foreground = if (enabled) Orbita.colors.fgOnAccent else Orbita.colors.fgQuaternary
    Box(
        modifier = Modifier
            .fillMaxWidth()
            // 52dp comfortably clears the 48dp accessibility minimum; this is
            // pressed without looking.
            .heightIn(min = Orbita.sizing.controlHeight)
            .clip(RoundedCornerShape(Orbita.radii.pill))
            .background(background)
            .clickable(enabled = enabled, role = Role.Button, onClick = onClick)
            .padding(Orbita.spacing.x4),
        contentAlignment = Alignment.Center,
    ) {
        Text(text = label, style = OrbitaType.title3, color = foreground)
    }
}
