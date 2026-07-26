package com.dax.assistant.ui.settings

import android.Manifest
import android.app.NotificationManager
import android.content.ComponentName
import android.content.Context
import android.content.pm.PackageManager
import android.os.Build
import androidx.core.content.ContextCompat
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.dax.assistant.R
import com.dax.assistant.capabilities.DaxNotificationListenerService
import com.dax.assistant.capabilities.NotificationHistory
import com.dax.assistant.core.network.BackendEndpointPolicy
import com.dax.assistant.data.auth.CapabilityNodeAuth
import com.dax.assistant.data.auth.CapabilityNodeCredentialStore
import com.dax.assistant.data.auth.CredentialStore
import com.dax.assistant.data.auth.EnrolResult
import com.dax.assistant.data.transport.CapabilityConnectionState
import com.dax.assistant.data.transport.CapabilityNodeSocket
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
import dagger.hilt.android.qualifiers.ApplicationContext
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
    val dirty: Boolean = false,
    val nodeEnrolled: Boolean = false,
    val nodeEnabled: Boolean = true,
    val nodePairingCode: String = "",
    val nodeEnrolling: Boolean = false,
    val nodeConnection: CapabilityConnectionState = CapabilityConnectionState.Disconnected,
    val notificationAccess: Boolean = false,
    val callPermission: Boolean = false,
)

@HiltViewModel
class SettingsViewModel @Inject constructor(
    private val api: MobileApiClient,
    private val preferences: AppPreferences,
    private val clientCredentials: CredentialStore,
    private val nodeCredentials: CapabilityNodeCredentialStore,
    private val nodeAuth: CapabilityNodeAuth,
    private val nodeSocket: CapabilityNodeSocket,
    private val notificationHistory: NotificationHistory,
    @ApplicationContext private val context: Context,
) : ViewModel() {
    private var savedConfig = MobileConfig()
    private val _state = MutableStateFlow(
        SettingsUiState(
            nodeEnrolled = nodeCredentials.isEnrolled,
            nodeEnabled = nodeCredentials.enabled,
            nodeConnection = nodeSocket.state.value,
            notificationAccess = hasNotificationAccess(),
            callPermission = hasCallPermission(),
        ),
    )
    val state: StateFlow<SettingsUiState> = _state.asStateFlow()

    init {
        viewModelScope.launch {
            preferences.state.collect { value -> _state.update { it.copy(preferences = value) } }
        }
        viewModelScope.launch {
            nodeSocket.state.collect { value ->
                _state.update { it.copy(nodeConnection = value) }
            }
        }
    }

    fun load() {
        if (_state.value.loading) return
        _state.update { it.copy(loading = true, error = null, saved = false) }
        viewModelScope.launch {
            when (val result = api.loadConfig()) {
                is MobileApiResult.Success -> _state.update {
                    savedConfig = result.value
                    it.copy(config = result.value, loading = false, loaded = true, dirty = false)
                }
                is MobileApiResult.Failed -> _state.update {
                    it.copy(loading = false, error = result.reason)
                }
            }
        }
    }

    fun update(transform: (MobileConfig) -> MobileConfig) {
        _state.update {
            val config = transform(it.config)
            it.copy(config = config, error = null, saved = false, dirty = config != savedConfig)
        }
    }

    fun setAppLanguage(value: AppLanguage) = preferences.setAppLanguage(value)

    fun setRecognitionMode(value: RecognitionMode) = preferences.setRecognitionMode(value)

    fun setRecognitionLanguage(value: RecognitionLanguage) = preferences.setRecognitionLanguage(value)

    fun setSpeechOutputMode(value: SpeechOutputMode) = preferences.setSpeechOutputMode(value)

    fun setTheme(value: ThemePreference) = preferences.setTheme(value)

    fun setFollowUpEnabled(value: Boolean) = preferences.setFollowUpEnabled(value)

    fun setSpeakChatReplies(value: Boolean) = preferences.setSpeakChatReplies(value)

    fun setNodePairingCode(value: String) {
        _state.update {
            it.copy(nodePairingCode = value.uppercase().filter(Char::isLetterOrDigit).take(8), error = null)
        }
    }

    fun applyNodePairingPayload(raw: String) {
        val payload = com.dax.assistant.ui.setup.PairingPayload.parse(raw)
        if (payload == null || payload.kind != com.dax.assistant.ui.setup.PairingKind.CAPABILITY_NODE) {
            _state.update { it.copy(error = context.getString(R.string.settings_phone_node_invalid_qr)) }
            return
        }
        val expected = BackendEndpointPolicy.normalize(clientCredentials.backendUrl)
        val supplied = BackendEndpointPolicy.normalize(payload.backendUrl)
        if (expected == null || supplied != expected) {
            _state.update { it.copy(error = context.getString(R.string.settings_phone_node_wrong_backend)) }
            return
        }
        if (!BackendEndpointPolicy.allowsCapabilityNode(payload.backendUrl)) {
            _state.update { it.copy(error = context.getString(R.string.settings_phone_node_https)) }
            return
        }
        _state.update { it.copy(nodePairingCode = payload.code, error = null) }
    }

    fun enrolPhoneNode() {
        val code = _state.value.nodePairingCode
        if (!com.dax.assistant.ui.setup.isValidPairingCode(code)) {
            _state.update { it.copy(error = context.getString(R.string.setup_error_code_invalid)) }
            return
        }
        if (!BackendEndpointPolicy.allowsCapabilityNode(clientCredentials.backendUrl)) {
            _state.update { it.copy(error = context.getString(R.string.settings_phone_node_https)) }
            return
        }
        _state.update { it.copy(nodeEnrolling = true, error = null) }
        viewModelScope.launch {
            when (val result = nodeAuth.enrol(code, "${Build.MODEL} phone")) {
                EnrolResult.Success -> {
                    _state.update {
                        it.copy(
                            nodeEnrolled = true,
                            nodeEnabled = true,
                            nodePairingCode = "",
                            nodeEnrolling = false,
                        )
                    }
                    nodeSocket.connect()
                }
                is EnrolResult.Failed -> _state.update {
                    it.copy(nodeEnrolling = false, error = result.reason)
                }
            }
        }
    }

    fun setPhoneNodeEnabled(enabled: Boolean) {
        nodeSocket.setEnabled(enabled)
        _state.update { it.copy(nodeEnabled = enabled) }
    }

    fun forgetPhoneNode() {
        nodeSocket.disconnect()
        nodeCredentials.clear()
        notificationHistory.clear()
        _state.update {
            it.copy(
                nodeEnrolled = false,
                nodeEnabled = true,
                nodePairingCode = "",
                nodeConnection = CapabilityConnectionState.Disconnected,
            )
        }
    }

    fun refreshPhoneNodePermissions() {
        val notificationAccess = hasNotificationAccess()
        val callPermission = hasCallPermission()
        val inventoryChanged = notificationAccess != _state.value.notificationAccess ||
            callPermission != _state.value.callPermission
        _state.update {
            it.copy(
                notificationAccess = notificationAccess,
                callPermission = callPermission,
            )
        }
        if (inventoryChanged) nodeSocket.refreshInventory()
    }

    private fun hasNotificationAccess(): Boolean =
        context.getSystemService(NotificationManager::class.java)
            .isNotificationListenerAccessGranted(
                ComponentName(context, DaxNotificationListenerService::class.java),
            )

    private fun hasCallPermission(): Boolean =
        ContextCompat.checkSelfPermission(context, Manifest.permission.CALL_PHONE) ==
            PackageManager.PERMISSION_GRANTED

    fun save() {
        if (_state.value.saving || !_state.value.dirty) return
        val config = _state.value.config
        _state.update { it.copy(saving = true, error = null, saved = false) }
        viewModelScope.launch {
            when (val result = api.saveConfig(config)) {
                is MobileApiResult.Success -> _state.update {
                    savedConfig = result.value
                    it.copy(config = result.value, saving = false, saved = true, dirty = false)
                }
                is MobileApiResult.Failed -> _state.update {
                    it.copy(saving = false, error = result.reason)
                }
            }
        }
    }
}
