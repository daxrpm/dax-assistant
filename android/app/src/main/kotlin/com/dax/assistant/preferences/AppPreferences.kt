package com.dax.assistant.preferences

import android.content.Context
import androidx.appcompat.app.AppCompatDelegate
import androidx.core.os.LocaleListCompat
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow

enum class AppLanguage(val storedValue: String, val languageTag: String) {
    ENGLISH("en", "en"),
    SPANISH("es", "es"),
    ;

    companion object {
        fun fromStored(value: String?) = entries.firstOrNull { it.storedValue == value } ?: ENGLISH
    }
}

enum class RecognitionMode(val storedValue: String) {
    ANDROID("android"),
    SERVER("server"),
    ;

    companion object {
        fun fromStored(value: String?) = entries.firstOrNull { it.storedValue == value } ?: ANDROID
    }
}

enum class SpeechOutputMode(val storedValue: String) {
    SERVER("server"),
    ANDROID("android"),
    ;

    companion object {
        fun fromStored(value: String?) = entries.firstOrNull { it.storedValue == value } ?: SERVER
    }
}

enum class RecognitionLanguage(val storedValue: String) {
    ENGLISH_US("en-US"),
    SPANISH_SPAIN("es-ES"),
    AUTO("auto"),
    ;

    companion object {
        fun fromStored(value: String?) = entries.firstOrNull { it.storedValue == value } ?: AUTO
    }

    fun languageTag(appLanguage: AppLanguage): String = when (this) {
        ENGLISH_US -> "en-US"
        SPANISH_SPAIN -> "es-ES"
        AUTO -> if (appLanguage == AppLanguage.SPANISH) "es-ES" else "en-US"
    }
}

enum class ThemePreference(val storedValue: String) {
    SYSTEM("system"),
    DARK("dark"),
    LIGHT("light"),
    ;

    companion object {
        fun fromStored(value: String?) = entries.firstOrNull { it.storedValue == value } ?: SYSTEM
    }
}

data class AppPreferenceState(
    val appLanguage: AppLanguage = AppLanguage.ENGLISH,
    val recognitionMode: RecognitionMode = RecognitionMode.ANDROID,
    val recognitionLanguage: RecognitionLanguage = RecognitionLanguage.AUTO,
    val speechOutputMode: SpeechOutputMode = SpeechOutputMode.SERVER,
    val theme: ThemePreference = ThemePreference.SYSTEM,
    val followUpEnabled: Boolean = true,
)

class AppPreferences(context: Context) {
    private val store = context.getSharedPreferences(FILE_NAME, Context.MODE_PRIVATE)
    private val _state = MutableStateFlow(read())
    val state: StateFlow<AppPreferenceState> = _state.asStateFlow()

    fun applyPersistedLanguage() = applyLanguage(_state.value.appLanguage)

    fun setAppLanguage(value: AppLanguage) {
        store.edit().putString(KEY_LANGUAGE, value.storedValue).apply()
        _state.value = _state.value.copy(appLanguage = value)
        applyLanguage(value)
    }

    fun setRecognitionMode(value: RecognitionMode) {
        store.edit().putString(KEY_RECOGNITION_MODE, value.storedValue).apply()
        _state.value = _state.value.copy(recognitionMode = value)
    }

    fun setRecognitionLanguage(value: RecognitionLanguage) {
        store.edit().putString(KEY_RECOGNITION_LANGUAGE, value.storedValue).apply()
        _state.value = _state.value.copy(recognitionLanguage = value)
    }

    fun setSpeechOutputMode(value: SpeechOutputMode) {
        store.edit().putString(KEY_SPEECH_OUTPUT_MODE, value.storedValue).apply()
        _state.value = _state.value.copy(speechOutputMode = value)
    }

    fun setTheme(value: ThemePreference) {
        store.edit().putString(KEY_THEME, value.storedValue).apply()
        _state.value = _state.value.copy(theme = value)
    }

    fun setFollowUpEnabled(value: Boolean) {
        store.edit().putBoolean(KEY_FOLLOW_UP, value).apply()
        _state.value = _state.value.copy(followUpEnabled = value)
    }

    private fun read() = AppPreferenceState(
        appLanguage = AppLanguage.fromStored(store.getString(KEY_LANGUAGE, null)),
        recognitionMode = RecognitionMode.fromStored(store.getString(KEY_RECOGNITION_MODE, null)),
        recognitionLanguage = RecognitionLanguage.fromStored(store.getString(KEY_RECOGNITION_LANGUAGE, null)),
        speechOutputMode = SpeechOutputMode.fromStored(store.getString(KEY_SPEECH_OUTPUT_MODE, null)),
        theme = ThemePreference.fromStored(store.getString(KEY_THEME, null)),
        followUpEnabled = store.getBoolean(KEY_FOLLOW_UP, true),
    )

    private fun applyLanguage(language: AppLanguage) {
        AppCompatDelegate.setApplicationLocales(LocaleListCompat.forLanguageTags(language.languageTag))
    }

    private companion object {
        const val FILE_NAME = "app_preferences"
        const val KEY_LANGUAGE = "app_language"
        const val KEY_RECOGNITION_MODE = "recognition_mode"
        const val KEY_RECOGNITION_LANGUAGE = "recognition_language"
        const val KEY_SPEECH_OUTPUT_MODE = "speech_output_mode"
        const val KEY_THEME = "theme"
        const val KEY_FOLLOW_UP = "voice_follow_up"
    }
}
