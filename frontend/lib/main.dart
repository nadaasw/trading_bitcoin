import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'dart:convert';
import 'dart:async';
import 'package:web_socket_channel/web_socket_channel.dart';

void main() {
  runApp(const MyApp());
}

class MyApp extends StatelessWidget {
  const MyApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        brightness: Brightness.dark,
        scaffoldBackgroundColor: const Color(0xFF1E2A45),
        colorScheme: ColorScheme.fromSeed(
          seedColor: Colors.blueAccent,
          brightness: Brightness.dark,
        ),
        sliderTheme: const SliderThemeData(
          thumbColor: Colors.blueAccent,
          activeTrackColor: Colors.lightBlue,
          inactiveTrackColor: Colors.white30,
        ),
        elevatedButtonTheme: ElevatedButtonThemeData(
          style: ElevatedButton.styleFrom(
            backgroundColor: Colors.blueAccent,
            foregroundColor: Colors.white,
            padding: EdgeInsets.symmetric(horizontal: 24, vertical: 12),
          ),
        ),
      ),
      home: const StrategyForm(),
    );
  }
}

class StrategyForm extends StatefulWidget {
  const StrategyForm({super.key});

  @override
  State<StrategyForm> createState() => _StrategyFormState();
}

class _StrategyFormState extends State<StrategyForm> {
  double lossCut = -4.0;
  double takeProfit = 1.5;
  int timeoutMinutes = 5;
  int durationMinutes = 60;
  double investRatio = 30.0;
  List<String> selectedCoins = [];
  List<String> availableCoins = [];
  String resultLog = "";

  bool isRunning = false;
  DateTime? startTime;
  Duration? elapsedTime;
  Duration? totalDuration;
  Duration? remainingTime;
  StreamSubscription? logSubscription;
  Timer? timer;

  @override
  void initState() {
    super.initState();
    fetchTopCoins();
  }

  Future<void> fetchTopCoins() async {
    try {
      final url = Uri.parse("http://127.0.0.1:8000/top-coins");
      final response = await http.get(url);

      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        setState(() {
          availableCoins = List<String>.from(data['top_coins']);
        });
      }
    } catch (e) {
      print("❌ HTTP 요청 에러: $e");
    }
  }

  void startStrategy() {
    setState(() {
      isRunning = true;
      resultLog = "전략 실행 중...";
      startTime = DateTime.now();
      totalDuration = Duration(minutes: durationMinutes);
      elapsedTime = Duration.zero;
      remainingTime = totalDuration;
    });

    timer = Timer.periodic(Duration(seconds: 1), (_) {
      setState(() {
        elapsedTime = DateTime.now().difference(startTime!);
        remainingTime = totalDuration! - elapsedTime!;
        if (remainingTime!.inSeconds <= 0) {
          isRunning = false;
          resultLog += "\n✅ 전략 자동 종료됨";
          timer?.cancel();
          logSubscription?.cancel();
        }
      });
    });

    final channel = WebSocketChannel.connect(
      Uri.parse('ws://127.0.0.1:8000/ws/logs'),
    );
    logSubscription = channel.stream.listen((message) {
      setState(() {
        resultLog += '\n$message';
      });
    });

    sendStrategy();
  }

  void stopStrategy() {
    setState(() {
      isRunning = false;
      resultLog += "\n⛔ 전략 수동 종료됨";
    });
    logSubscription?.cancel();
    logSubscription = null;
    timer?.cancel();
    timer = null;
  }

  Future<void> sendStrategy() async {
    final url = Uri.parse("http://127.0.0.1:8000/start-strategy");
    final body = {
      "loss_cut": lossCut,
      "take_profit": takeProfit,
      "timeout_minutes": timeoutMinutes,
      "duration_minutes": durationMinutes,
      "invest_ratio": investRatio,
      "candidates": selectedCoins,
    };

    try {
      await http.post(
        url,
        headers: {"Content-Type": "application/json"},
        body: jsonEncode(body),
      );
    } catch (e) {
      setState(() {
        resultLog += "\n❌ 전략 요청 실패: $e";
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        backgroundColor: Colors.black,
        title: const Text("비트코인 자동매매 설정"),
      ),
      body: Center(
        child: Card(
          elevation: 8,
          margin: const EdgeInsets.all(20),
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(20)),
          color: const Color(0xFF2C3E5A),
          child: Padding(
            padding: const EdgeInsets.all(20),
            child: SingleChildScrollView(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  buildSlider("손절률 (%)", lossCut, -10.0, 0.0, (val) => setState(() => lossCut = val)),
                  buildSlider("익절률 (%)", takeProfit, 0.0, 5.0, (val) => setState(() => takeProfit = val)),
                  buildIntSlider("감시 시간 (분)", timeoutMinutes, 1, 30, (val) => setState(() => timeoutMinutes = val)),
                  buildIntSlider("실행 시간 (분)", durationMinutes, 10, 240, (val) => setState(() => durationMinutes = val)),
                  buildSlider("투자 비율 (%)", investRatio, 1.0, 100.0, (val) => setState(() => investRatio = val)),
                  const SizedBox(height: 20),
                  const Text("코인 리스트 (최대 20개 중 다중 선택)", style: TextStyle(fontWeight: FontWeight.bold)),
                  availableCoins.isEmpty
                      ? const Padding(
                          padding: EdgeInsets.symmetric(vertical: 12),
                          child: Text("코인 데이터를 불러오는 중입니다...", style: TextStyle(color: Colors.white)),
                        )
                      : Wrap(
                          spacing: 6,
                          children: availableCoins.map((coin) => FilterChip(
                            label: Text(coin),
                            selected: selectedCoins.contains(coin),
                            onSelected: (bool selected) {
                              setState(() {
                                if (selected) {
                                  selectedCoins.add(coin);
                                } else {
                                  selectedCoins.remove(coin);
                                }
                              });
                            },
                          )).toList(),
                        ),
                  const SizedBox(height: 24),
                  if (!isRunning)
                    Center(
                      child: ElevatedButton(
                        onPressed: startStrategy,
                        child: const Text("전략 실행"),
                      ),
                    )
                  else
                    Row(
                      mainAxisAlignment: MainAxisAlignment.center,
                      children: [
                        ElevatedButton(
                          onPressed: stopStrategy,
                          style: ElevatedButton.styleFrom(backgroundColor: Colors.red),
                          child: const Text("멈추기"),
                        ),
                        const SizedBox(width: 20),
                        Text("⏱️ 경과: ${elapsedTime?.inMinutes ?? 0}분 ${elapsedTime?.inSeconds.remainder(60) ?? 0}초"),
                        const SizedBox(width: 20),
                        Text("⏳ 남은: ${remainingTime?.inMinutes ?? 0}분 ${remainingTime?.inSeconds.remainder(60) ?? 0}초"),
                      ],
                    ),
                  const SizedBox(height: 24),
                  const Text("결과 로그:", style: TextStyle(fontWeight: FontWeight.bold)),
                  const SizedBox(height: 8),
                  Container(
                    padding: const EdgeInsets.all(12),
                    width: double.infinity,
                    decoration: BoxDecoration(
                      color: Colors.black38,
                      borderRadius: BorderRadius.circular(12),
                    ),
                    child: SelectableText(resultLog),
                  ),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }

  Widget buildSlider(String label, double value, double min, double max, Function(double) onChanged) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text("$label: ${value.toStringAsFixed(2)}"),
        SizedBox(
          width: 300,
          child: Slider(
            value: value,
            min: min,
            max: max,
            divisions: 100,
            label: value.toStringAsFixed(2),
            onChanged: onChanged,
          ),
        ),
      ],
    );
  }

  Widget buildIntSlider(String label, int value, int min, int max, Function(int) onChanged) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text("$label: $value"),
        SizedBox(
          width: 300,
          child: Slider(
            value: value.toDouble(),
            min: min.toDouble(),
            max: max.toDouble(),
            divisions: max - min,
            label: value.toString(),
            onChanged: (double newVal) => onChanged(newVal.round()),
          ),
        ),
      ],
    );
  }
}
