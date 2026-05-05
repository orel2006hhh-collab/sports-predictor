name: Update Daily Matches

on:
  schedule:
    - cron: '0 6 * * *'
  workflow_dispatch:

permissions:
  contents: write

jobs:
  update-matches:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout repository
        uses: actions/checkout@v4
      
      - name: Create data directory
        run: mkdir -p data
      
      - name: Generate matches.json with Python
        run: |
          python << 'EOF'
      import json
      from datetime import datetime, timedelta
      
      today = datetime.now()
      tomorrow = today + timedelta(days=1)
      
      today_str = today.strftime('%d.%m.%Y')
      tomorrow_str = tomorrow.strftime('%d.%m.%Y')
      
      matches = [
          {'sport': 'nhl', 'home': 'Philadelphia Flyers', 'away': 'Carolina Hurricanes', 'league': 'НХЛ', 'prob': 72, 'winner': 'Carolina Hurricanes', 'date': today_str, 'time': '02:00 МСК', 'series': 'Плей-офф', 'weather': 'Ясно', 'motivation': 'Филадельфия обязана выигрывать'},
          {'sport': 'vhl', 'home': 'Югра', 'away': 'Нефтяник', 'league': 'ВХЛ', 'prob': 78, 'winner': 'Югра', 'date': today_str, 'time': '19:00 МСК', 'series': 'Финал', 'weather': 'Ясно', 'motivation': 'Югра ведёт 3-0'},
          {'sport': 'nba', 'home': 'Oklahoma City Thunder', 'away': 'Los Angeles Lakers', 'league': 'НБА', 'prob': 72, 'winner': 'Oklahoma City Thunder', 'date': today_str, 'time': '05:30 МСК', 'series': 'Плей-офф', 'weather': 'Крытая арена', 'motivation': 'Лейкерс без Джеймса'},
          {'sport': 'cricket', 'home': 'Gujarat Titans', 'away': 'Mumbai Indians', 'league': 'IPL', 'prob': 68, 'winner': 'Gujarat Titans', 'date': today_str, 'time': '21:30 МСК', 'series': 'Тур 2026', 'weather': '40°C', 'motivation': 'Титаны в топ-4'},
          {'sport': 'cricket', 'home': 'Kolkata Knight Riders', 'away': 'Chennai Super Kings', 'league': 'IPL', 'prob': 72, 'winner': 'Kolkata Knight Riders', 'date': tomorrow_str, 'time': '21:30 МСК', 'series': 'Тур 2026', 'weather': '35°C', 'motivation': 'KKR борется за 1 место'}
      ]
      
      output = {
          'lastUpdated': datetime.now().isoformat(),
          'matches': matches,
          'dateInfo': {'today': today_str, 'tomorrow': tomorrow_str}
      }
      
      with open('data/matches.json', 'w', encoding='utf-8') as f:
          json.dump(output, f, ensure_ascii=False, indent=2)
      
      print(f'✅ Обновлено! Матчей: {len(matches)}')
      print(f'   Сегодня: {today_str}')
      print(f'   Завтра: {tomorrow_str}')
      EOF
      
      - name: Show generated file
        run: cat data/matches.json
      
      - name: Commit and push changes
        run: |
          git config --local user.email "github-actions[bot]@users.noreply.github.com"
          git config --local user.name "github-actions[bot]"
          git add data/matches.json
          git diff --cached --quiet || git commit -m "🤖 Автообновление матчей [skip ci]"
          git push
