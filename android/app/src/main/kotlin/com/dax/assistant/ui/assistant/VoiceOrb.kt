package com.dax.assistant.ui.assistant

import androidx.compose.animation.core.LinearEasing
import androidx.compose.animation.core.RepeatMode
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.animation.core.tween
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.size
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalAccessibilityManager
import com.dax.assistant.assistant.AssistantState
import com.dax.assistant.ui.design.Orbita
import kotlin.math.sin

/**
 * The voice surface.
 *
 * A direct descendant of the desktop's pseudo-3D orb, rebuilt for a phone: the
 * desktop draws z-sorted particles and source-specific wave rings at 60fps on a
 * machine that is plugged in, which is the wrong trade on a battery. This keeps
 * the identity — radial depth, indigo accent, motion that means something — and
 * spends far less to do it.
 *
 * Every state has a distinct motion signature, so the orb is readable at a
 * glance without reading the label under it: listening breathes, thinking
 * pulses faster and tighter, speaking swells. That mapping is the point; an orb
 * that animates identically in every state is decoration.
 */
@Composable
fun VoiceOrb(
    state: AssistantState,
    modifier: Modifier = Modifier,
) {
    val colors = Orbita.colors
    val reduceMotion =
        LocalAccessibilityManager.current?.let { false } ?: false

    val tone = when (state) {
        is AssistantState.Listening, is AssistantState.ConnectingAudio -> colors.accent
        is AssistantState.Transcribing, is AssistantState.Processing -> colors.purple
        is AssistantState.AwaitingApproval -> colors.warning
        is AssistantState.Speaking -> colors.success
        is AssistantState.Disconnected -> colors.fgQuaternary
        is AssistantState.Failed -> colors.danger
        is AssistantState.Idle -> colors.accent
    }

    // Period, not amplitude, carries the meaning: a fast cycle reads as work in
    // progress, a slow one as waiting.
    val periodMillis = when (state) {
        is AssistantState.Idle -> 4200
        is AssistantState.ConnectingAudio -> 1200
        is AssistantState.Listening -> 2400
        is AssistantState.Transcribing -> 1400
        is AssistantState.Processing -> 1000
        is AssistantState.AwaitingApproval -> 2000
        is AssistantState.Speaking -> 1600
        is AssistantState.Disconnected, is AssistantState.Failed -> 5200
    }

    val transition = rememberInfiniteTransition(label = "orb")
    val phase by transition.animateFloat(
        initialValue = 0f,
        targetValue = 1f,
        animationSpec = infiniteRepeatable(
            animation = tween(periodMillis, easing = LinearEasing),
            repeatMode = RepeatMode.Restart,
        ),
        label = "phase",
    )

    val energy = when (state) {
        is AssistantState.Listening -> if (state.speechDetected) 1f else 0.55f
        is AssistantState.Processing, is AssistantState.Transcribing -> 0.8f
        is AssistantState.Speaking -> 0.9f
        is AssistantState.Idle -> 0.32f
        else -> 0.4f
    }

    Box(modifier = modifier.size(Orbita.sizing.orbDiameter)) {
        Canvas(Modifier.size(Orbita.sizing.orbDiameter)) {
            val centre = Offset(size.width / 2f, size.height / 2f)
            val maxRadius = size.minDimension / 2f
            val breath = if (reduceMotion) 0f else sin(phase * 2f * Math.PI.toFloat())
            val core = maxRadius * (0.44f + 0.05f * breath * energy)

            // Outer halo. Depth comes from the gradient falloff, never a
            // stroked ring — the Orbita rule about borders applies here too.
            drawCircle(
                brush = Brush.radialGradient(
                    colors = listOf(
                        tone.copy(alpha = 0.26f * energy),
                        tone.copy(alpha = 0.08f * energy),
                        Color.Transparent,
                    ),
                    center = centre,
                    radius = maxRadius,
                ),
                radius = maxRadius,
                center = centre,
            )

            // Two expanding rings, offset in phase so there is always one
            // visible mid-flight. Only while something is actually happening.
            if (!reduceMotion && state !is AssistantState.Idle) {
                listOf(0f, 0.5f).forEach { offset ->
                    val p = (phase + offset) % 1f
                    drawCircle(
                        color = tone.copy(alpha = (1f - p) * 0.20f * energy),
                        radius = core + (maxRadius - core) * p,
                        center = centre,
                    )
                }
            }

            // The body.
            drawCircle(
                brush = Brush.radialGradient(
                    colors = listOf(
                        tone.copy(alpha = 0.95f),
                        tone.copy(alpha = 0.62f),
                        tone.copy(alpha = 0.34f),
                    ),
                    center = Offset(centre.x - core * 0.22f, centre.y - core * 0.28f),
                    radius = core * 1.5f,
                ),
                radius = core,
                center = centre,
            )

            // Specular highlight, offset up-left. This is what sells it as a
            // sphere rather than a flat disc.
            drawCircle(
                brush = Brush.radialGradient(
                    colors = listOf(Color.White.copy(alpha = 0.30f), Color.Transparent),
                    center = Offset(centre.x - core * 0.34f, centre.y - core * 0.40f),
                    radius = core * 0.62f,
                ),
                radius = core * 0.62f,
                center = Offset(centre.x - core * 0.34f, centre.y - core * 0.40f),
            )
        }
    }
}
