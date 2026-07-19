package com.dax.assistant.diagnostics

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.dax.assistant.core.log.DaxLog
import dagger.hilt.android.lifecycle.HiltViewModel
import javax.inject.Inject
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

data class DiagnosticsUiState(
    val report: CapabilityReport = CapabilityReport(),
    val running: Boolean = false,
    val permissionsGranted: Boolean = false,
    /**
     * Set once a media button reaches the app. Held separately from the report
     * because it arrives asynchronously from a physical press rather than from
     * the probe run.
     */
    val mediaButtonSeen: String? = null,
    val listeningForMediaButton: Boolean = false,
)

@HiltViewModel
class DiagnosticsViewModel @Inject constructor(
    private val probe: CapabilityProbe,
) : ViewModel() {

    private val _state = MutableStateFlow(DiagnosticsUiState())
    val state: StateFlow<DiagnosticsUiState> = _state.asStateFlow()

    fun onPermissionsResult(granted: Boolean) {
        _state.update { it.copy(permissionsGranted = granted) }
    }

    fun runProbe() {
        if (_state.value.running) return
        _state.update { it.copy(running = true, report = CapabilityReport()) }
        viewModelScope.launch {
            val result = runCatching {
                // Progress updates land as each check completes, so a probe
                // that hangs on one step still shows what already passed.
                probe.run { partial -> _state.update { it.copy(report = partial) } }
            }
            result.onFailure { DaxLog.e(TAG, "Capability probe failed", it) }
            _state.update {
                it.copy(running = false, report = result.getOrDefault(it.report))
            }
        }
    }

    fun onMediaButton(description: String) {
        DaxLog.i(TAG, "Media button observed: $description")
        _state.update {
            it.copy(
                mediaButtonSeen = description,
                listeningForMediaButton = false,
                report = it.report.with(
                    CheckId.MEDIA_BUTTON,
                    CheckStatus.PASS,
                    description,
                ),
            )
        }
    }

    fun armMediaButtonListener() {
        _state.update { it.copy(listeningForMediaButton = true, mediaButtonSeen = null) }
    }

    private companion object {
        const val TAG = "DiagnosticsVM"
    }
}
