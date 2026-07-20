package com.dax.assistant.ui

import android.content.Intent
import android.provider.Settings
import androidx.compose.foundation.layout.BoxWithConstraints
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.systemBarsPadding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ChatBubble
import androidx.compose.material.icons.filled.GraphicEq
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material3.Icon
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.Alignment
import androidx.compose.ui.draw.clip
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.semantics.selected
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.navigation.NavHostController
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.currentBackStackEntryAsState
import androidx.navigation.compose.rememberNavController
import com.dax.assistant.R
import com.dax.assistant.assistant.AssistantState
import com.dax.assistant.assistant.Turn
import com.dax.assistant.diagnostics.DiagnosticsUiState
import com.dax.assistant.diagnostics.DiagnosticsViewModel
import com.dax.assistant.ui.assistant.AssistantScreen
import com.dax.assistant.ui.conversations.ConversationsScreen
import com.dax.assistant.ui.diagnostics.DiagnosticsScreen
import com.dax.assistant.ui.settings.SettingsScreen
import com.dax.assistant.ui.settings.SettingsViewModel
import com.dax.assistant.ui.design.Orbita
import com.dax.assistant.ui.design.OrbitaType

private enum class MainDestination(
    val route: String,
    val label: Int,
    val icon: ImageVector,
) {
    Assistant("assistant", R.string.nav_assistant, Icons.Filled.GraphicEq),
    Conversations("conversations", R.string.nav_conversations, Icons.Filled.ChatBubble),
    SettingsPage("settings", R.string.nav_settings, Icons.Filled.Settings),
}

private const val DIAGNOSTICS_ROUTE = "settings/diagnostics"

@Composable
fun MainNavigation(
    assistantState: AssistantState,
    history: List<Turn>,
    diagnosticsState: DiagnosticsUiState,
    diagnostics: DiagnosticsViewModel,
    onTrigger: () -> Unit,
    onCancel: () -> Unit,
    onApprove: (String) -> Unit,
    onRequestPermissions: () -> Unit,
    onForgetEverything: () -> Unit,
    onDeviceRecognition: Boolean,
) {
    val navController = rememberNavController()
    BoxWithConstraints(Modifier.fillMaxSize()) {
        if (maxWidth >= 720.dp) {
            Row(Modifier.fillMaxSize().background(Orbita.colors.bgWindow).padding(Orbita.spacing.x3)) {
                DestinationRail(navController, Modifier.systemBarsPadding())
                MainGraph(
                    navController, assistantState, history, diagnosticsState, diagnostics,
                    onTrigger, onCancel, onApprove, onRequestPermissions,
                    onForgetEverything, onDeviceRecognition,
                    Modifier.weight(1f).padding(start = Orbita.spacing.x3),
                )
            }
        } else {
            Box(Modifier.fillMaxSize().background(Orbita.colors.bgWindow)) {
                MainGraph(
                    navController, assistantState, history, diagnosticsState, diagnostics,
                    onTrigger, onCancel, onApprove, onRequestPermissions,
                    onForgetEverything, onDeviceRecognition,
                    Modifier.fillMaxSize().padding(bottom = 88.dp),
                )
                DestinationBar(navController, Modifier.align(Alignment.BottomCenter).systemBarsPadding())
            }
        }
    }
}

@Composable
private fun MainGraph(
    navController: NavHostController,
    assistantState: AssistantState,
    history: List<Turn>,
    diagnosticsState: DiagnosticsUiState,
    diagnostics: DiagnosticsViewModel,
    onTrigger: () -> Unit,
    onCancel: () -> Unit,
    onApprove: (String) -> Unit,
    onRequestPermissions: () -> Unit,
    onForgetEverything: () -> Unit,
    onDeviceRecognition: Boolean,
    modifier: Modifier,
) {
    val context = LocalContext.current
    NavHost(navController, startDestination = MainDestination.Assistant.route, modifier = modifier) {
        composable(MainDestination.Assistant.route) {
            AssistantScreen(
                assistantState, history, onTrigger, onCancel, onApprove,
                onOpenSettings = { navController.navigate(MainDestination.SettingsPage.route) },
            )
        }
        composable(MainDestination.Conversations.route) { ConversationsScreen(history) }
        composable(MainDestination.SettingsPage.route) {
            val viewModel: SettingsViewModel = hiltViewModel()
            val state by viewModel.state.collectAsStateWithLifecycle()
            SettingsScreen(
                state = state,
                onLoad = viewModel::load,
                onUpdate = viewModel::update,
                onSave = viewModel::save,
                onAppLanguageChange = viewModel::setAppLanguage,
                onRecognitionModeChange = viewModel::setRecognitionMode,
                onRecognitionLanguageChange = viewModel::setRecognitionLanguage,
                onThemeChange = viewModel::setTheme,
                onOpenDiagnostics = { navController.navigate(DIAGNOSTICS_ROUTE) },
            )
        }
        composable(DIAGNOSTICS_ROUTE) {
            DiagnosticsScreen(
                state = diagnosticsState,
                onRunProbe = diagnostics::runProbe,
                onRequestPermissions = onRequestPermissions,
                onBack = { navController.popBackStack() },
                onOpenAssistantSettings = {
                    runCatching {
                        context.startActivity(
                            Intent(Settings.ACTION_VOICE_INPUT_SETTINGS).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK),
                        )
                    }
                },
                onForgetEverything = onForgetEverything,
                onDeviceRecognition = onDeviceRecognition,
            )
        }
    }
}

@Composable
private fun DestinationBar(navController: NavHostController, modifier: Modifier = Modifier) {
    val route = navController.currentBackStackEntryAsState().value?.destination?.route
    Row(
        modifier.padding(horizontal = Orbita.spacing.x3, vertical = Orbita.spacing.x2)
            .fillMaxWidth().clip(RoundedCornerShape(Orbita.radii.xxl))
            .background(Orbita.colors.bgPanel).padding(Orbita.spacing.x1),
        horizontalArrangement = Arrangement.spacedBy(Orbita.spacing.x1),
    ) {
        MainDestination.entries.forEach { destination ->
            DestinationItem(
                modifier = Modifier.weight(1f),
                destination = destination,
                selected = route == destination.route,
                onClick = { navController.open(destination) },
            )
        }
    }
}

@Composable
private fun DestinationRail(navController: NavHostController, modifier: Modifier = Modifier) {
    val route = navController.currentBackStackEntryAsState().value?.destination?.route
    Column(
        modifier.width(88.dp).clip(RoundedCornerShape(Orbita.radii.xxl))
            .background(Orbita.colors.bgPanel).padding(Orbita.spacing.x2),
        verticalArrangement = Arrangement.spacedBy(Orbita.spacing.x2),
    ) {
        MainDestination.entries.forEach { destination ->
            DestinationItem(
                modifier = Modifier.fillMaxWidth(),
                destination = destination,
                selected = route == destination.route,
                onClick = { navController.open(destination) },
            )
        }
    }
}

@Composable
private fun DestinationItem(
    destination: MainDestination,
    selected: Boolean,
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
) {
    val color = if (selected) Orbita.colors.fgPrimary else Orbita.colors.fgTertiary
    Column(
        modifier.clip(RoundedCornerShape(Orbita.radii.xl))
            .background(if (selected) Orbita.colors.bgElevated else Orbita.colors.bgPanel)
            .clickable(role = Role.Tab, onClick = onClick)
            .semantics { this.selected = selected }
            .heightIn(min = 60.dp).padding(vertical = Orbita.spacing.x2),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.Center,
    ) {
        Icon(destination.icon, contentDescription = null, tint = color, modifier = Modifier.size(20.dp))
        Text(stringResource(destination.label), style = OrbitaType.caption, color = color)
    }
}

private fun NavHostController.open(destination: MainDestination) {
    navigate(destination.route) {
        popUpTo(graph.startDestinationId) { saveState = true }
        launchSingleTop = true
        restoreState = true
    }
}
