package com.dax.assistant.ui.design

import android.database.ContentObserver
import android.os.Handler
import android.os.Looper
import android.provider.Settings
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.platform.LocalContext

/**
 * Android's equivalent of `prefers-reduced-motion`, which the desktop honours in
 * CSS.
 *
 * There is no first-class Compose API for this, so it reads the global animator
 * scale — the setting "Remove animations" in accessibility actually writes. It
 * observes rather than samples, because the user may turn animations off while
 * a surface is open and an orb that keeps breathing after that is precisely the
 * thing they asked to stop.
 */
@Composable
fun rememberReduceMotion(): Boolean {
    val context = LocalContext.current
    val resolver = context.contentResolver
    fun readScale() = runCatching {
        Settings.Global.getFloat(resolver, Settings.Global.ANIMATOR_DURATION_SCALE) == 0f
    }.getOrDefault(false)

    var reduceMotion by remember(resolver) { mutableStateOf(readScale()) }
    DisposableEffect(resolver) {
        val observer = object : ContentObserver(Handler(Looper.getMainLooper())) {
            override fun onChange(selfChange: Boolean) {
                reduceMotion = readScale()
            }
        }
        resolver.registerContentObserver(
            Settings.Global.getUriFor(Settings.Global.ANIMATOR_DURATION_SCALE),
            false,
            observer,
        )
        onDispose { resolver.unregisterContentObserver(observer) }
    }
    return reduceMotion
}
