/*
 * LibrePods - AirPods liberated from Apple’s ecosystem
 *
 * Copyright (C) 2025 LibrePods Contributors
 *
 * This program is free software: you can redistribute it and/or modify
 * it under the terms of the GNU Affero General Public License as published
 * by the Free Software Foundation, either version 3 of the License.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU Affero General Public License for more details.
 *
 * You should have received a copy of the GNU Affero General Public License
 * along with this program. If not, see <https://www.gnu.org/licenses/>.
 */

@file:OptIn(ExperimentalEncodingApi::class)

package me.kavishdevar.librepods.services


import android.accessibilityservice.AccessibilityService
import android.util.Log
import android.view.accessibility.AccessibilityEvent
import kotlin.io.encoding.ExperimentalEncodingApi

private const val TAG="AppListenerService"

val cameraPackages = setOf(
    "com.google.android.GoogleCamera",
    "com.sec.android.app.camera",
    "com.android.camera",
    "com.oppo.camera",
    "com.motorola.camera2",
    "org.codeaurora.snapcam",
    "com.nothing.camera"
)

var cameraOpen = false

class AppListenerService : AccessibilityService() {
    override fun onAccessibilityEvent(ev: AccessibilityEvent?) {
        try {
            if (ev?.eventType == AccessibilityEvent.TYPE_WINDOW_STATE_CHANGED) {
                val pkg = ev.packageName?.toString() ?: return
                if (pkg == "com.android.systemui") return // after camera opens, systemui is opened, probably for the privacy indicators
                Log.d(TAG, "Package: $pkg, cameraOpen: $cameraOpen")
                if (pkg in cameraPackages) {
                    Log.d(TAG, "Camera app opened: $pkg")
                    if (!cameraOpen) cameraOpen = true
                    ServiceManager.getService()?.cameraOpened()
                } else {
                    if (cameraOpen) {
                        cameraOpen = false
                        ServiceManager.getService()?.cameraClosed()
                    } else {
                        Log.d(TAG, "ignoring")
                    }
                }
                // Log.d(TAG, "Opened: $pkg")
            }
        } catch(e: Exception) {
            Log.e(TAG, "Error in onAccessibilityEvent: ${e.message}")
        }
    }

    override fun onInterrupt() {}
}