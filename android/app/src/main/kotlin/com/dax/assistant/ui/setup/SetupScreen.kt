package com.dax.assistant.ui.setup

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.systemBarsPadding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.OutlinedTextFieldDefaults
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.text.input.KeyboardCapitalization
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.semantics.Role
import com.dax.assistant.ui.SetupUiState
import com.dax.assistant.ui.design.Orbita
import com.dax.assistant.ui.design.OrbitaType

/**
 * First run: point the phone at a backend and pair it.
 *
 * The phone never asks for the account password. A client that is already
 * signed in — the desktop app or the web UI — mints a one-time pairing code,
 * and this screen redeems it once for a device credential that lives in the
 * keystore. That is why the copy talks about a code from another device rather
 * than offering a password field: there is deliberately nowhere to type one.
 */
@Composable
fun SetupScreen(
    state: SetupUiState,
    onUrlChange: (String) -> Unit,
    onCodeChange: (String) -> Unit,
    onEnrol: () -> Unit,
    modifier: Modifier = Modifier,
) {
    Column(
        modifier = modifier
            .fillMaxSize()
            .background(Orbita.colors.bgWindow)
            .systemBarsPadding()
            .verticalScroll(rememberScrollState())
            .padding(horizontal = Orbita.spacing.edge, vertical = Orbita.spacing.x8),
    ) {
        Text(text = "Connect to Dax", style = OrbitaType.largeTitle, color = Orbita.colors.fgPrimary)
        Spacer(Modifier.height(Orbita.spacing.x2))
        Text(
            text = "Dax runs on your own machine. This phone pairs with it using " +
                "a one-time code — it never stores your password.",
            style = OrbitaType.callout,
            color = Orbita.colors.fgTertiary,
        )

        Spacer(Modifier.height(Orbita.spacing.x8))

        Field(
            label = "Backend address",
            value = state.backendUrl,
            onValueChange = onUrlChange,
            placeholder = "https://dax.example  ·  http://192.168.1.20:8420",
            keyboardType = KeyboardType.Uri,
        )

        Spacer(Modifier.height(Orbita.spacing.x5))

        Field(
            label = "Pairing code",
            value = state.pairingCode,
            onValueChange = onCodeChange,
            placeholder = "8 characters",
            capitalization = KeyboardCapitalization.Characters,
        )
        Spacer(Modifier.height(Orbita.spacing.x2))
        Text(
            text = "On the desktop app or web UI: Settings → Devices → Pair a device.",
            style = OrbitaType.footnote,
            color = Orbita.colors.fgQuaternary,
        )

        state.error?.let { error ->
            Spacer(Modifier.height(Orbita.spacing.x4))
            Box(
                Modifier
                    .fillMaxWidth()
                    .clip(RoundedCornerShape(Orbita.radii.lg))
                    .background(Orbita.colors.danger.copy(alpha = 0.14f))
                    .padding(Orbita.spacing.x4),
            ) {
                Text(text = error, style = OrbitaType.callout, color = Orbita.colors.danger)
            }
        }

        Spacer(Modifier.height(Orbita.spacing.x8))

        Box(
            modifier = Modifier
                .fillMaxWidth()
                .heightIn(min = Orbita.sizing.controlHeight)
                .clip(RoundedCornerShape(Orbita.radii.pill))
                .background(
                    if (state.enrolling) Orbita.colors.bgElevated else Orbita.colors.accent,
                )
                .clickable(enabled = !state.enrolling, role = Role.Button, onClick = onEnrol)
                .padding(Orbita.spacing.x4),
            contentAlignment = Alignment.Center,
        ) {
            Text(
                text = if (state.enrolling) "Pairing…" else "Pair this phone",
                style = OrbitaType.title3,
                color = if (state.enrolling) {
                    Orbita.colors.fgQuaternary
                } else {
                    Orbita.colors.fgOnAccent
                },
            )
        }
    }
}

@Composable
private fun Field(
    label: String,
    value: String,
    onValueChange: (String) -> Unit,
    placeholder: String,
    keyboardType: KeyboardType = KeyboardType.Text,
    capitalization: KeyboardCapitalization = KeyboardCapitalization.None,
) {
    Column(verticalArrangement = Arrangement.spacedBy(Orbita.spacing.x2)) {
        Text(text = label.uppercase(), style = OrbitaType.label, color = Orbita.colors.fgTertiary)
        OutlinedTextField(
            value = value,
            onValueChange = onValueChange,
            placeholder = {
                Text(placeholder, style = OrbitaType.callout, color = Orbita.colors.fgQuaternary)
            },
            singleLine = true,
            textStyle = OrbitaType.mono.copy(color = Orbita.colors.fgPrimary),
            keyboardOptions = KeyboardOptions(
                keyboardType = keyboardType,
                capitalization = capitalization,
                autoCorrectEnabled = false,
            ),
            shape = RoundedCornerShape(Orbita.radii.lg),
            colors = OutlinedTextFieldDefaults.colors(
                focusedContainerColor = Orbita.colors.bgInset,
                unfocusedContainerColor = Orbita.colors.bgInset,
                focusedBorderColor = Orbita.colors.accent,
                unfocusedBorderColor = Orbita.colors.separator,
                cursorColor = Orbita.colors.accent,
            ),
            modifier = Modifier.fillMaxWidth(),
        )
    }
}
