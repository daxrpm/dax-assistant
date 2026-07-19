package com.dax.assistant.ui

import android.Manifest
import android.content.pm.PackageManager
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.core.content.ContextCompat
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.dax.assistant.diagnostics.DiagnosticsViewModel
import com.dax.assistant.ui.design.OrbitaTheme
import com.dax.assistant.ui.diagnostics.DiagnosticsScreen
import dagger.hilt.android.AndroidEntryPoint

/**
 * Entry point.
 *
 * Diagnostics is the whole surface for now, on purpose: until the capability
 * probe has run on real hardware there is nothing honest for a voice screen to
 * promise. The assistant surface lands on top of a proven audio route, not
 * beside an unproven one.
 */
@AndroidEntryPoint
class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        setContent {
            OrbitaTheme {
                DaxRoot()
            }
        }
    }
}

private val requiredPermissions = arrayOf(
    Manifest.permission.RECORD_AUDIO,
    Manifest.permission.BLUETOOTH_CONNECT,
)

@Composable
private fun DaxRoot(viewModel: DiagnosticsViewModel = hiltViewModel()) {
    val state by viewModel.state.collectAsStateWithLifecycle()
    val context = androidx.compose.ui.platform.LocalContext.current

    val launcher = rememberLauncherForActivityResult(
        ActivityResultContracts.RequestMultiplePermissions(),
    ) { granted ->
        // RECORD_AUDIO is the one the probe cannot proceed without;
        // BLUETOOTH_CONNECT only downgrades the HFP check to SKIPPED.
        viewModel.onPermissionsResult(granted[Manifest.permission.RECORD_AUDIO] == true)
    }

    LaunchedEffect(Unit) {
        val alreadyGranted = ContextCompat.checkSelfPermission(
            context,
            Manifest.permission.RECORD_AUDIO,
        ) == PackageManager.PERMISSION_GRANTED
        viewModel.onPermissionsResult(alreadyGranted)
    }

    DiagnosticsScreen(
        state = state,
        onRunProbe = viewModel::runProbe,
        onRequestPermissions = { launcher.launch(requiredPermissions) },
    )
}
