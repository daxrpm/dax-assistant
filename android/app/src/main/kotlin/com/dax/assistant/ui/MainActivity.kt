package com.dax.assistant.ui

import android.Manifest
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Build
import android.os.Bundle
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.ui.platform.LocalContext
import androidx.core.content.ContextCompat
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.appcompat.app.AppCompatActivity
import com.dax.assistant.diagnostics.DiagnosticsViewModel
import com.dax.assistant.preferences.AppPreferences
import com.dax.assistant.preferences.ThemePreference
import com.dax.assistant.service.AssistantService
import com.dax.assistant.trigger.MediaButtonTrigger
import com.dax.assistant.ui.design.OrbitaTheme
import com.dax.assistant.ui.setup.SetupScreen
import com.journeyapps.barcodescanner.ScanContract
import com.journeyapps.barcodescanner.ScanOptions
import dagger.hilt.android.AndroidEntryPoint
import javax.inject.Inject
import kotlinx.coroutines.flow.MutableStateFlow

@AndroidEntryPoint
class MainActivity : AppCompatActivity() {

    @Inject
    lateinit var mediaButtons: MediaButtonTrigger

    @Inject
    lateinit var preferences: AppPreferences

    private val pairingDeepLink = MutableStateFlow<String?>(null)

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        pairingDeepLink.value = intent?.dataString
        enableEdgeToEdge()
        setContent {
            val preferenceState by preferences.state.collectAsStateWithLifecycle()
            val systemDark = isSystemInDarkTheme()
            val darkTheme = when (preferenceState.theme) {
                ThemePreference.SYSTEM -> systemDark
                ThemePreference.DARK -> true
                ThemePreference.LIGHT -> false
            }
            OrbitaTheme(darkTheme = darkTheme) {
                DaxApp(pairingDeepLink.collectAsStateWithLifecycle().value)
            }
        }
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        setIntent(intent)
        pairingDeepLink.value = intent.dataString
    }

    override fun onStart() {
        super.onStart()
        // Armed while the app is in the foreground so a watch or headset media
        // key can start a turn. The session must be active to receive keys at
        // all, and holding one permanently would take them from music apps.
        mediaButtons.start()
    }

    override fun onStop() {
        mediaButtons.stop()
        super.onStop()
    }
}

private val requiredPermissions = buildList {
    add(Manifest.permission.RECORD_AUDIO)
    add(Manifest.permission.BLUETOOTH_CONNECT)
    if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
        add(Manifest.permission.POST_NOTIFICATIONS)
    }
}.toTypedArray()

@Composable
private fun DaxApp(
    pairingDeepLink: String?,
    viewModel: AppViewModel = hiltViewModel(),
    diagnostics: DiagnosticsViewModel = hiltViewModel(),
) {
    val context = LocalContext.current
    val setup by viewModel.setup.collectAsStateWithLifecycle()
    val assistantState by viewModel.controller.state.collectAsStateWithLifecycle()
    val history by viewModel.controller.history.collectAsStateWithLifecycle()
    val diagnosticsState by diagnostics.state.collectAsStateWithLifecycle()

    var micGranted by remember { mutableStateOf(false) }

    val scanner = rememberLauncherForActivityResult(ScanContract()) { result ->
        result.contents?.let(viewModel::applyPairingPayload)
    }

    val permissionLauncher = rememberLauncherForActivityResult(
        ActivityResultContracts.RequestMultiplePermissions(),
    ) { granted ->
        micGranted = granted[Manifest.permission.RECORD_AUDIO] == true
        diagnostics.onPermissionsResult(micGranted)
        if (micGranted && setup.enrolled) AssistantService.ensureRunning(context)
    }

    LaunchedEffect(Unit) {
        micGranted = ContextCompat.checkSelfPermission(
            context,
            Manifest.permission.RECORD_AUDIO,
        ) == PackageManager.PERMISSION_GRANTED
        diagnostics.onPermissionsResult(micGranted)
        if (!micGranted) permissionLauncher.launch(requiredPermissions)
    }

    LaunchedEffect(setup.enrolled, micGranted) {
        if (setup.enrolled) {
            viewModel.connect()
            // The service is what keeps the socket alive and makes a
            // background-triggered turn legal, so it starts as soon as the
            // device is paired and the microphone is granted.
            if (micGranted) AssistantService.ensureRunning(context)
        }
    }

    LaunchedEffect(pairingDeepLink) {
        pairingDeepLink?.let(viewModel::applyPairingPayload)
    }

    if (!setup.enrolled) {
        SetupScreen(
            state = setup,
            onUrlChange = viewModel::onBackendUrlChanged,
            onCodeChange = viewModel::onPairingCodeChanged,
            onEnrol = viewModel::enrol,
            onScanQr = {
                scanner.launch(
                    ScanOptions().setDesiredBarcodeFormats(ScanOptions.QR_CODE)
                        .setBeepEnabled(false).setOrientationLocked(false),
                )
            },
        )
    } else {
        MainNavigation(
            assistantState = assistantState,
            history = history,
            diagnosticsState = diagnosticsState,
            diagnostics = diagnostics,
            onTrigger = {
                if (micGranted) {
                    viewModel.controller.startTurn()
                } else {
                    permissionLauncher.launch(requiredPermissions)
                }
            },
            onCancel = viewModel.controller::cancel,
            onApprove = viewModel.controller::resolveApproval,
            onRequestPermissions = { permissionLauncher.launch(requiredPermissions) },
            onForgetEverything = viewModel::forgetEverything,
            onDeviceRecognition = viewModel.onDeviceRecognition,
        )
    }
}
