import 'package:flutter/material.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'app_theme.dart';
import 'session_home.dart';

const _kThemePrefKey = 'app_theme_mode';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  final prefs = await SharedPreferences.getInstance();
  final saved = prefs.getString(_kThemePrefKey);
  final ThemeMode initial = switch (saved) {
    'light' => ThemeMode.light,
    'dark' => ThemeMode.dark,
    _ => ThemeMode.system,
  };
  runApp(SmartCamApp(initialThemeMode: initial));
}

class SmartCamApp extends StatelessWidget {
  const SmartCamApp({
    super.key,
    this.initialThemeMode = ThemeMode.system,
  });

  /// Сохранённый режим из SharedPreferences; смена только в настройках ОС.
  final ThemeMode initialThemeMode;

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Smart Cam',
      debugShowCheckedModeBanner: false,
      theme: AppTheme.light(),
      darkTheme: AppTheme.dark(),
      themeMode: initialThemeMode,
      home: const SessionHomePage(),
    );
  }
}
