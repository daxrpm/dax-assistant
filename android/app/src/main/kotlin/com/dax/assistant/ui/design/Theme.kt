package com.dax.assistant.ui.design

import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.LocalTextStyle
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Typography
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.runtime.staticCompositionLocalOf
import androidx.compose.material3.LocalContentColor
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.LineHeightStyle
import androidx.compose.ui.unit.em
import androidx.compose.ui.unit.sp

/**
 * The Órbita type ramp.
 *
 * Two things from the desktop matter and are preserved. First, the sans/mono
 * split *is* the typographic personality: mono is reserved for machine facts —
 * ids, tool names, levels, metrics — and never used for prose. Second,
 * uppercase machine labels get tracking; body text never does.
 *
 * Sizes step up slightly from the desktop values. The desktop is read at
 * arm's length on a large display; a phone is read at 30cm, often in motion,
 * sometimes one-handed, and the body size has to survive that.
 */
object OrbitaType {
    private val sans = FontFamily.SansSerif
    private val monoFamily = FontFamily.Monospace

    private val tightLineHeight = LineHeightStyle(
        alignment = LineHeightStyle.Alignment.Center,
        trim = LineHeightStyle.Trim.None,
    )

    val largeTitle = TextStyle(
        fontFamily = sans,
        fontSize = 30.sp,
        lineHeight = 36.sp,
        fontWeight = FontWeight.SemiBold,
        letterSpacing = (-0.011).em,
        lineHeightStyle = tightLineHeight,
    )
    val title1 = TextStyle(
        fontFamily = sans,
        fontSize = 24.sp,
        lineHeight = 31.sp,
        fontWeight = FontWeight.SemiBold,
        letterSpacing = (-0.011).em,
        lineHeightStyle = tightLineHeight,
    )
    val title2 = TextStyle(
        fontFamily = sans,
        fontSize = 19.sp,
        lineHeight = 25.sp,
        fontWeight = FontWeight.Medium,
        lineHeightStyle = tightLineHeight,
    )
    val title3 = TextStyle(
        fontFamily = sans,
        fontSize = 16.sp,
        lineHeight = 22.sp,
        fontWeight = FontWeight.Medium,
        lineHeightStyle = tightLineHeight,
    )
    val body = TextStyle(
        fontFamily = sans,
        fontSize = 16.sp,
        lineHeight = 23.sp,
        lineHeightStyle = tightLineHeight,
    )

    /**
     * Assistant and user turns. Looser leading than [body] because this is the
     * text people actually read at length, often while walking.
     */
    val conversation = TextStyle(
        fontFamily = sans,
        fontSize = 17.sp,
        lineHeight = 26.sp,
        lineHeightStyle = tightLineHeight,
    )

    /**
     * Live transcription. Lighter than a settled turn so the eye can tell
     * "still being heard" from "recorded", without relying on colour alone.
     */
    val transcript = TextStyle(
        fontFamily = sans,
        fontSize = 20.sp,
        lineHeight = 28.sp,
        fontWeight = FontWeight.Light,
        lineHeightStyle = tightLineHeight,
    )
    val callout = TextStyle(
        fontFamily = sans,
        fontSize = 15.sp,
        lineHeight = 21.sp,
        lineHeightStyle = tightLineHeight,
    )
    val subhead = TextStyle(
        fontFamily = sans,
        fontSize = 14.sp,
        lineHeight = 19.sp,
        lineHeightStyle = tightLineHeight,
    )
    val footnote = TextStyle(
        fontFamily = sans,
        fontSize = 13.sp,
        lineHeight = 17.sp,
        lineHeightStyle = tightLineHeight,
    )
    val caption = TextStyle(
        fontFamily = sans,
        fontSize = 12.sp,
        lineHeight = 16.sp,
        lineHeightStyle = tightLineHeight,
    )

    /** Uppercase machine label. Tracking is what makes it read as a label. */
    val label = TextStyle(
        fontFamily = sans,
        fontSize = 12.sp,
        lineHeight = 16.sp,
        fontWeight = FontWeight.Medium,
        letterSpacing = 0.08.em,
        lineHeightStyle = tightLineHeight,
    )

    /** Machine facts only: ids, tool names, levels, metrics. Never prose. */
    val mono = TextStyle(
        fontFamily = monoFamily,
        fontSize = 13.sp,
        lineHeight = 19.sp,
        lineHeightStyle = tightLineHeight,
    )
    val monoSmall = TextStyle(
        fontFamily = monoFamily,
        fontSize = 12.sp,
        lineHeight = 17.sp,
        lineHeightStyle = tightLineHeight,
    )
}

val LocalOrbitaColors = staticCompositionLocalOf { OrbitaDarkColors }
val LocalOrbitaSpacing = staticCompositionLocalOf { OrbitaDefaultSpacing }
val LocalOrbitaRadii = staticCompositionLocalOf { OrbitaDefaultRadii }
val LocalOrbitaSizing = staticCompositionLocalOf { OrbitaDefaultSizing }
val LocalOrbitaElevation = staticCompositionLocalOf { OrbitaDefaultElevation }
val LocalOrbitaMotion = staticCompositionLocalOf { OrbitaDefaultMotion }

/**
 * Accessors so call sites read `Orbita.colors.accent` rather than reaching
 * through a composition local by name.
 */
object Orbita {
    val colors: OrbitaColors
        @Composable get() = LocalOrbitaColors.current
    val spacing: OrbitaSpacing
        @Composable get() = LocalOrbitaSpacing.current
    val radii: OrbitaRadii
        @Composable get() = LocalOrbitaRadii.current
    val sizing: OrbitaSizing
        @Composable get() = LocalOrbitaSizing.current
    val elevation: OrbitaElevation
        @Composable get() = LocalOrbitaElevation.current
    val motion: OrbitaMotion
        @Composable get() = LocalOrbitaMotion.current
}

@Composable
fun OrbitaTheme(
    darkTheme: Boolean = isSystemInDarkTheme(),
    content: @Composable () -> Unit,
) {
    val colors = if (darkTheme) OrbitaDarkColors else OrbitaLightColors

    // Material3 is present for a handful of primitives (ripple, text field
    // plumbing, sheet scaffolding). Its scheme is mapped onto Órbita so a
    // stray Material default can never introduce an off-palette colour.
    val material = if (darkTheme) {
        darkColorScheme(
            primary = colors.accent,
            onPrimary = colors.fgOnAccent,
            secondary = colors.purple,
            onSecondary = colors.fgOnAccent,
            secondaryContainer = colors.bgSelected,
            onSecondaryContainer = colors.fgPrimary,
            tertiary = colors.info,
            onTertiary = colors.fgOnAccent,
            background = colors.bgWindow,
            onBackground = colors.fgPrimary,
            surface = colors.bgPanel,
            onSurface = colors.fgPrimary,
            surfaceVariant = colors.bgElevated,
            onSurfaceVariant = colors.fgSecondary,
            surfaceTint = colors.accent,
            inverseSurface = colors.fgPrimary,
            inverseOnSurface = colors.bgWindow,
            inversePrimary = colors.accentPressed,
            error = colors.danger,
            onError = colors.fgOnAccent,
            errorContainer = colors.danger.copy(alpha = 0.16f),
            onErrorContainer = colors.danger,
            outline = colors.separator,
            outlineVariant = colors.separator,
            scrim = androidx.compose.ui.graphics.Color.Black,
        )
    } else {
        lightColorScheme(
            primary = colors.accent,
            onPrimary = colors.fgOnAccent,
            secondary = colors.purple,
            onSecondary = colors.fgOnAccent,
            secondaryContainer = colors.bgSelected,
            onSecondaryContainer = colors.fgPrimary,
            tertiary = colors.info,
            onTertiary = colors.fgOnAccent,
            background = colors.bgWindow,
            onBackground = colors.fgPrimary,
            surface = colors.bgPanel,
            onSurface = colors.fgPrimary,
            surfaceVariant = colors.bgElevated,
            onSurfaceVariant = colors.fgSecondary,
            surfaceTint = colors.accent,
            inverseSurface = colors.fgPrimary,
            inverseOnSurface = colors.bgWindow,
            inversePrimary = colors.accentPressed,
            error = colors.danger,
            onError = colors.fgOnAccent,
            errorContainer = colors.danger.copy(alpha = 0.12f),
            onErrorContainer = colors.danger,
            outline = colors.separator,
            outlineVariant = colors.separator,
            scrim = androidx.compose.ui.graphics.Color.Black,
        )
    }

    CompositionLocalProvider(
        LocalOrbitaColors provides colors,
        LocalContentColor provides colors.fgPrimary,
        LocalTextStyle provides OrbitaType.body.copy(color = colors.fgPrimary),
    ) {
        MaterialTheme(
            colorScheme = material,
            typography = Typography(
                displayLarge = OrbitaType.largeTitle,
                headlineMedium = OrbitaType.title1,
                titleLarge = OrbitaType.title2,
                titleMedium = OrbitaType.title3,
                bodyLarge = OrbitaType.body,
                bodyMedium = OrbitaType.callout,
                labelLarge = OrbitaType.subhead,
                labelMedium = OrbitaType.label,
                labelSmall = OrbitaType.caption,
            ),
            content = content,
        )
    }
}
