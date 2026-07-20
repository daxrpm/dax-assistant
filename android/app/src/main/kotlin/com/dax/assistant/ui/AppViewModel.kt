package com.dax.assistant.ui

import android.content.Context
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.dax.assistant.assistant.AssistantController
import com.dax.assistant.audio.SpeechRecognition
import com.dax.assistant.core.network.BackendEndpointPolicy
import com.dax.assistant.data.auth.BackendAuth
import com.dax.assistant.data.auth.CredentialStore
import com.dax.assistant.data.auth.EnrolResult
import com.dax.assistant.data.transport.ChatSocket
import com.dax.assistant.ui.setup.PairingPayload
import com.dax.assistant.ui.setup.isValidPairingCode
import com.dax.assistant.R
import dagger.hilt.android.lifecycle.HiltViewModel
import dagger.hilt.android.qualifiers.ApplicationContext
import javax.inject.Inject
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

data class SetupUiState(
    val backendUrl: String = "",
    val pairingCode: String = "",
    val enrolling: Boolean = false,
    val error: String? = null,
    val enrolled: Boolean = false,
)

@HiltViewModel
class AppViewModel @Inject constructor(
    val controller: AssistantController,
    private val credentials: CredentialStore,
    private val auth: BackendAuth,
    private val socket: ChatSocket,
    private val recognition: SpeechRecognition,
    @ApplicationContext private val context: Context,
) : ViewModel() {

    private val _setup = MutableStateFlow(
        SetupUiState(
            backendUrl = credentials.backendUrl,
            enrolled = credentials.isEnrolled,
        ),
    )
    val setup: StateFlow<SetupUiState> = _setup.asStateFlow()

    val onDeviceRecognition: Boolean get() = recognition.onDeviceAvailable

    fun onBackendUrlChanged(value: String) {
        _setup.update { it.copy(backendUrl = value, error = null) }
    }

    fun onPairingCodeChanged(value: String) {
        _setup.update { it.copy(pairingCode = value.uppercase(), error = null) }
    }

    fun applyPairingPayload(raw: String) {
        val payload = PairingPayload.parse(raw)
        if (payload == null) {
            _setup.update { it.copy(error = context.getString(R.string.setup_error_invalid_qr)) }
            return
        }
        _setup.update {
            it.copy(backendUrl = payload.backendUrl, pairingCode = payload.code, error = null)
        }
    }

    fun enrol() {
        val current = _setup.value
        if (current.backendUrl.isBlank()) {
            _setup.update { it.copy(error = context.getString(R.string.setup_error_backend_required)) }
            return
        }
        val url = BackendEndpointPolicy.normalize(current.backendUrl)
        if (url == null) {
            _setup.update {
                it.copy(error = context.getString(R.string.setup_error_backend_invalid))
            }
            return
        }
        if (!isValidPairingCode(current.pairingCode)) {
            _setup.update { it.copy(error = context.getString(R.string.setup_error_code_invalid)) }
            return
        }

        credentials.backendUrl = url
        _setup.update { it.copy(enrolling = true, error = null) }

        viewModelScope.launch {
            when (val result = auth.enrol(current.pairingCode, android.os.Build.MODEL)) {
                is EnrolResult.Success -> {
                    _setup.update {
                        it.copy(enrolling = false, enrolled = true, pairingCode = "")
                    }
                    socket.connect()
                }

                is EnrolResult.Failed -> _setup.update {
                    it.copy(enrolling = false, error = result.reason)
                }
            }
        }
    }

    /** Forgets the device credential and every stored turn. */
    fun forgetEverything() {
        socket.disconnect()
        credentials.clear()
        _setup.value = SetupUiState()
    }

    fun connect() {
        if (credentials.isEnrolled) socket.connect()
    }
}
