package com.dax.assistant.ui.settings

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.dax.assistant.mobileapi.MobileApiClient
import com.dax.assistant.mobileapi.MobileApiResult
import com.dax.assistant.mobileapi.MobileConfig
import com.dax.assistant.preferences.AppLanguage
import com.dax.assistant.preferences.AppPreferenceState
import com.dax.assistant.preferences.AppPreferences
import com.dax.assistant.preferences.RecognitionLanguage
import com.dax.assistant.preferences.RecognitionMode
import com.dax.assistant.preferences.SpeechOutputMode
import com.dax.assistant.preferences.ThemePreference
import dagger.hilt.android.lifecycle.HiltViewModel
import javax.inject.Inject
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

data class SettingsUiState(
    val config: MobileConfig = MobileConfig(),
    val loading: Boolean = false,
    val saving: Boolean = false,
    val loaded: Boolean = false,
    val saved: Boolean = false,
    val error: String? = null,
    val preferences: AppPreferenceState = AppPreferenceState(),
)

@HiltViewModel
class SettingsViewModel @Inject constructor(
    private val api: MobileApiClient,
    private val preferences: AppPreferences,
) : ViewModel() {
    private val _state = MutableStateFlow(SettingsUiState())
    val state: StateFlow<SettingsUiState> = _state.asStateFlow()

    init {
        viewModelScope.launch {
            preferences.state.collect { value -> _state.update { it.copy(preferences = value) } }
        }
    }

    fun load() {
        if (_state.value.loading) return
        _state.update { it.copy(loading = true, error = null, saved = false) }
        viewModelScope.launch {
            when (val result = api.loadConfig()) {
                is MobileApiResult.Success -> _state.update {
                    it.copy(config = result.value, loading = false, loaded = true)
                }
                is MobileApiResult.Failed -> _state.update {
                    it.copy(loading = false, error = result.reason)
                }
            }
        }
    }

    fun update(transform: (MobileConfig) -> MobileConfig) {
        _state.update { it.copy(config = transform(it.config), error = null, saved = false) }
    }

    fun setAppLanguage(value: AppLanguage) = preferences.setAppLanguage(value)

    fun setRecognitionMode(value: RecognitionMode) = preferences.setRecognitionMode(value)

    fun setRecognitionLanguage(value: RecognitionLanguage) = preferences.setRecognitionLanguage(value)

    fun setSpeechOutputMode(value: SpeechOutputMode) = preferences.setSpeechOutputMode(value)

    fun setTheme(value: ThemePreference) = preferences.setTheme(value)

    fun setFollowUpEnabled(value: Boolean) = preferences.setFollowUpEnabled(value)

    fun save() {
        if (_state.value.saving) return
        val config = _state.value.config
        _state.update { it.copy(saving = true, error = null, saved = false) }
        viewModelScope.launch {
            when (val result = api.saveConfig(config)) {
                is MobileApiResult.Success -> _state.update {
                    it.copy(config = result.value, saving = false, saved = true)
                }
                is MobileApiResult.Failed -> _state.update {
                    it.copy(saving = false, error = result.reason)
                }
            }
        }
    }
}
