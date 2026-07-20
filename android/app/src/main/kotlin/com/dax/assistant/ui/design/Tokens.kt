package com.dax.assistant.ui.design

import androidx.compose.runtime.Immutable
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp

/**
 * Órbita, ported from `desktop/src/design/tokens.css`.
 *
 * The desktop file states three rules that make the product read as an
 * instrument rather than a web page, and they carry over unchanged:
 *
 *  1. Depth comes from shadow and elevation, never from a border.
 *  2. Radii are large. Nothing interactive goes below 10dp; panels sit at 18dp.
 *  3. Space is generous.
 *
 * What does *not* carry over is the layout. The desktop is a command deck with
 * a sidebar and dense rows; the phone is one hand, one thumb, and a voice
 * surface. Same palette, same type ramp, same personality — different
 * composition. Values are duplicated rather than generated because a build-time
 * dependency between a Vite app and an Android app would cost more than it
 * saves; `OrbitaTokensTest` pins the ones that must not drift.
 */
@Immutable
data class OrbitaColors(
    val bgWindow: Color,
    val bgContent: Color,
    val bgPanel: Color,
    val bgElevated: Color,
    val bgInset: Color,
    val bgHover: Color,
    val bgActive: Color,
    val bgSelected: Color,
    val fgPrimary: Color,
    val fgSecondary: Color,
    val fgTertiary: Color,
    val fgQuaternary: Color,
    val fgOnAccent: Color,
    val separator: Color,
    val accent: Color,
    val accentHover: Color,
    val accentPressed: Color,
    val accentDim: Color,
    val accentGlow: Color,
    val success: Color,
    val warning: Color,
    val danger: Color,
    val info: Color,
    val purple: Color,
    val focusRing: Color,
    val isLight: Boolean,
)

/**
 * Dark is the default palette, exactly as on the desktop: the ground is a deep
 * blue-biased near-black and every surface floats above it.
 */
val OrbitaDarkColors = OrbitaColors(
    bgWindow = Color(0xFF05070B),
    bgContent = Color(0xFF0D1219),
    bgPanel = Color(0xFF151B25),
    bgElevated = Color(0xFF1C2430),
    bgInset = Color(0xFF090D13),
    bgHover = Color(0x10DAE4FF),
    bgActive = Color(0x1ADAE4FF),
    bgSelected = Color(0xFF283653),
    fgPrimary = Color(0xFFF0F2F7),
    fgSecondary = Color(0xFFB7BFCE),
    fgTertiary = Color(0xFF9AA4B5),
    fgQuaternary = Color(0xFF828C9E),
    fgOnAccent = Color(0xFF0A0F24),
    separator = Color(0x10DAE4FF),
    accent = Color(0xFF6E8BFF),
    accentHover = Color(0xFF8AA1FF),
    accentPressed = Color(0xFF5673E8),
    accentDim = Color(0x246E8BFF),
    accentGlow = Color(0x666E8BFF),
    success = Color(0xFF4FD1A0),
    warning = Color(0xFFE8B44C),
    danger = Color(0xFFFF6B6B),
    info = Color(0xFF6E8BFF),
    purple = Color(0xFFA78BFA),
    focusRing = Color(0x8C6E8BFF),
    isLight = false,
)

/**
 * The light palette is a genuine second design, not an inversion: the same
 * floating architecture on a cool paper ground, with the accent darkened so it
 * still holds contrast on white.
 */
val OrbitaLightColors = OrbitaColors(
    bgWindow = Color(0xFFE4E7ED),
    bgContent = Color(0xFFF9FAFC),
    bgPanel = Color(0xFFFFFFFF),
    bgElevated = Color(0xFFFFFFFF),
    bgInset = Color(0xFFEDF0F5),
    bgHover = Color(0x0E19243E),
    bgActive = Color(0x1719243E),
    bgSelected = Color(0xFFDDE4FF),
    fgPrimary = Color(0xFF171A22),
    fgSecondary = Color(0xFF4E586B),
    fgTertiary = Color(0xFF586377),
    fgQuaternary = Color(0xFF626C7F),
    fgOnAccent = Color(0xFFFFFFFF),
    separator = Color(0x12101428),
    accent = Color(0xFF4E6AE8),
    accentHover = Color(0xFF3F5AD4),
    accentPressed = Color(0xFF3550BD),
    accentDim = Color(0x1F4E6AE8),
    accentGlow = Color(0x524E6AE8),
    success = Color(0xFF12A071),
    warning = Color(0xFFB47908),
    danger = Color(0xFFD84343),
    info = Color(0xFF4E6AE8),
    purple = Color(0xFF7C56D4),
    focusRing = Color(0x804E6AE8),
    isLight = true,
)

/** 4pt subdivisions on an 8pt grid, matching the desktop scale. */
@Immutable
data class OrbitaSpacing(
    val x1: Dp = 4.dp,
    val x2: Dp = 8.dp,
    val x3: Dp = 12.dp,
    val x4: Dp = 16.dp,
    val x5: Dp = 20.dp,
    val x6: Dp = 24.dp,
    val x8: Dp = 32.dp,
    val x10: Dp = 40.dp,
    val x12: Dp = 48.dp,
    val x16: Dp = 64.dp,
    /**
     * The screen edge. Wider than the desktop gutter because a thumb needs
     * somewhere to rest that is not a control.
     */
    val edge: Dp = 20.dp,
)

@Immutable
data class OrbitaRadii(
    val xs: Dp = 6.dp,
    val sm: Dp = 8.dp,
    /** Floor for anything interactive — below this it reads as a web widget. */
    val md: Dp = 10.dp,
    val lg: Dp = 12.dp,
    val xl: Dp = 18.dp,
    val xxl: Dp = 24.dp,
    val pill: Dp = 999.dp,
)

/**
 * Touch targets. 48dp is the Android accessibility minimum; the primary voice
 * control is far larger because it is the one thing you press without looking.
 */
@Immutable
data class OrbitaSizing(
    val minTouchTarget: Dp = 48.dp,
    val controlHeight: Dp = 52.dp,
    val orbDiameter: Dp = 208.dp,
    val orbDiameterCompact: Dp = 136.dp,
)

@Immutable
data class OrbitaElevation(
    val level1: Dp = 5.dp,
    val level2: Dp = 12.dp,
    val level3: Dp = 22.dp,
    val level4: Dp = 38.dp,
)

@Immutable
data class OrbitaMotion(
    val instantMillis: Int = 80,
    val fastMillis: Int = 140,
    val normalMillis: Int = 220,
    val slowMillis: Int = 340,
    val hudMillis: Int = 420,
)

val OrbitaDefaultSpacing = OrbitaSpacing()
val OrbitaDefaultRadii = OrbitaRadii()
val OrbitaDefaultSizing = OrbitaSizing()
val OrbitaDefaultElevation = OrbitaElevation()
val OrbitaDefaultMotion = OrbitaMotion()
