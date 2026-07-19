package com.dax.assistant.ui

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import com.dax.assistant.ui.design.Orbita
import com.dax.assistant.ui.design.OrbitaTheme
import com.dax.assistant.ui.design.OrbitaType
import dagger.hilt.android.AndroidEntryPoint

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

@Composable
private fun DaxRoot() {
    Box(
        modifier = Modifier
            .fillMaxSize()
            .background(Orbita.colors.bgWindow),
        contentAlignment = Alignment.Center,
    ) {
        Text(text = "Dax", style = OrbitaType.largeTitle, color = Orbita.colors.fgPrimary)
    }
}
