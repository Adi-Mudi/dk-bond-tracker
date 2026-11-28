import 'package:flutter/material.dart';

void main() {
  runApp(const DkBondTrackerApp());
}

class DkBondTrackerApp extends StatelessWidget {
  const DkBondTrackerApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'DK Bond Tracker',
      debugShowCheckedModeBanner: false,
      home: const Scaffold(
        body: Center(
          child: Text('DK Bond Tracker'),
        ),
      ),
    );
  }
}
