package com.dax.assistant.ui

import android.Manifest
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Build
import android.os.Bundle
import android.provider.Settings
import androidx.activity.ComponentActivity
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
import androidx.compose.ui.platform.LocalContext
import androidx.core.content.ContextCompat
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.dax.assistant.diagnostics.DiagnosticsViewModel
import com.dax.assistant.service.AssistantService
import com.dax.assistant.trigger.MediaButtonTrigger
import com.dax.assistant.ui.assistant.AssistantScreen
import com.dax.assistant.ui.design.OrbitaTheme
import com.dax.assistant.ui.diagnostics.DiagnosticsScreen
import com.dax.assistant.ui.setup.SetupScreen
import dagger.hilt.android.AndroidEntryPoint
import javax.inject.Inject

private enum class Screen { SETUP, ASSISTANT, DIAGNOSTICS }

@AndroidEntryPoint
class MainActivity : ComponentActivity() {

    @Inject
    lateinit var mediaButtons: MediaButtonTrigger

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        setContent { OrbitaTheme { DaxApp() } }
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
    viewModel: AppViewModel = hiltViewModel(),
    diagnostics: DiagnosticsViewModel = hiltViewModel(),
) {
    val context = LocalContext.current
    val setup by viewModel.setup.collectAsStateWithLifecycle()
    val assistantState by viewModel.controller.state.collectAsStateWithLifecycle()
    val history by viewModel.controller.history.collectAsStateWithLifecycle()
    val diagnosticsState by diagnostics.state.collectAsStateWithLifecycle()

    var screen by remember { mutableStateOf(Screen.SETUP) }
    var micGranted by remember { mutableStateOf(false) }

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
            screen = Screen.ASSISTANT
            viewModel.connect()
            // The service is what keeps the socket alive and makes a
            // background-triggered turn legal, so it starts as soon as the
            // device is paired and the microphone is granted.
            if (micGranted) AssistantService.ensureRunning(context)
        } else {
            screen = Screen.SETUP
        }
    }

    when (screen) {
        Screen.SETUP -> SetupScreen(
            state = setup,
            onUrlChange = viewModel::onBackendUrlChanged,
            onCodeChange = viewModel::onPairingCodeChanged,
            onEnrol = viewModel::enrol,
        )

        Screen.ASSISTANT -> AssistantScreen(
            state = assistantState,
            history = history,
            onTrigger = {
                if (micGranted) {
                    viewModel.controller.startTurn()
                } else {
                    permissionLauncher.launch(requiredPermissions)
                }
            },
            onCancel = viewModel.controller::cancel,
            onApprove = viewModel.controller::resolveApproval,
            onOpenSettings = { screen = Screen.DIAGNOSTICS },
        )

        Screen.DIAGNOSTICS -> DiagnosticsScreen(
            state = diagnosticsState,
            onRunProbe = diagnostics::runProbe,
            onRequestPermissions = { permissionLauncher.launch(requiredPermissions) },
            onBack = { screen = if (setup.enrolled) Screen.ASSISTANT else Screen.SETUP },
            onOpenAssistantSettings = {
                // The role cannot be requested programmatically; the user picks
                // Dax in Settings. Deep-linking is as close as an app can get.
                runCatching {
                    context.startActivity(
                        Intent(Settings.ACTION_VOICE_INPUT_SETTINGS)
                            .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK),
                    )
                }
            },
            onForgetEverything = viewModel::forgetEverything,
            onDeviceRecognition = viewModel.onDeviceRecognition,
        )
    }
}
