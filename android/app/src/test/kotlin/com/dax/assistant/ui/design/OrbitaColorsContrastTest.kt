package com.dax.assistant.ui.design

import androidx.compose.ui.graphics.Color
import kotlin.math.pow
import org.junit.Assert.assertTrue
import org.junit.Test

class OrbitaColorsContrastTest {
    @Test
    fun `settings text and chips meet AA contrast in both palettes`() {
        listOf(OrbitaDarkColors, OrbitaLightColors).forEach { colors ->
            assertContrast(colors.fgPrimary, colors.bgPanel, 4.5f)
            assertContrast(colors.fgTertiary, colors.bgPanel, 4.5f)
            assertContrast(colors.fgSecondary, colors.bgInset, 4.5f)
            assertContrast(colors.fgPrimary, colors.bgSelected, 4.5f)
            assertContrast(colors.fgPrimary, colors.bgContent, 4.5f)
            assertContrast(colors.fgOnAccent, colors.accent, 4.5f)
            assertContrast(colors.fgQuaternary, colors.bgElevated, 3f)
        }
    }

    private fun assertContrast(foreground: Color, background: Color, minimum: Float) {
        val lighter = maxOf(foreground.luminance(), background.luminance())
        val darker = minOf(foreground.luminance(), background.luminance())
        val ratio = (lighter + 0.05f) / (darker + 0.05f)
        assertTrue("Expected contrast >= $minimum, was $ratio", ratio >= minimum)
    }

    private fun Color.luminance(): Float {
        fun linear(value: Float): Float =
            if (value <= 0.04045f) value / 12.92f else ((value + 0.055f) / 1.055f).pow(2.4f)

        return 0.2126f * linear(red) + 0.7152f * linear(green) + 0.0722f * linear(blue)
    }
}
