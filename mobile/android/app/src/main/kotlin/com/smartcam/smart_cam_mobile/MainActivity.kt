package com.smartcam.smart_cam_mobile

import android.os.Bundle
import androidx.core.view.WindowCompat
import io.flutter.embedding.android.FlutterActivity

class MainActivity : FlutterActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        // Align native window with Flutter edge-to-edge / immersive UI (status & nav bars).
        WindowCompat.setDecorFitsSystemWindows(window, false)
    }
}
