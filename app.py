# ========================================
# ✅ Импорты
# ========================================
from flask import Flask, render_template_string, request, jsonify
from flask_cors import CORS
import pandas as pd
import swisseph as swe
import datetime
import pytz
from timezonefinder import TimezoneFinder
from math import floor

# ========================================
# ✅ Конфигурация
# ========================================
CITY_FILE = "worldcities.csv"  # Файл должен лежать в той же папке!
swe.set_sid_mode(swe.SIDM_LAHIRI)
tf = TimezoneFinder()
cities_df = pd.read_csv(CITY_FILE)

app = Flask(__name__)
CORS(app)

# ========================================
# ✅ HTML-шаблон
# ========================================
HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
  <title>🪐 Ведический гороскоп</title>
  <style>
    input[type="text"] { width: 300px; padding: 8px; }
    ul { list-style: none; padding: 0; border: 1px solid #ccc; max-height: 150px; overflow-y: auto; width: 300px; }
    li { padding: 5px; cursor: pointer; }
    li:hover { background: #eee; }
    button { margin-top: 10px; padding: 8px 12px; }
    pre { background: #f9f9f9; padding: 10px; }
    svg { border: 1px solid #000; margin: 20px; }
    text { font-family: Arial, sans-serif; fill: #0033cc; font-weight: bold; }
    .result-container { display: flex; gap: 40px; align-items: flex-start; }
  </style>
</head>
<body>
  <div id="form-container">
    <form id="form">
      <label>Имя:</label><br>
      <input type="text" id="nameInput" name="name" value="{{ name or '' }}"><br><br>
      <label>Дата рождения:</label><br>
      <input type="text" id="dateInput" name="date" value="{{ date or '' }}" placeholder="ДДММГГГГ или ДД-ММ-ГГГГ"><br><br>
      <label>Время рождения:</label><br>
      <input type="text" id="timeInput" name="time" value="{{ time or '' }}" placeholder="HHMM или HH:MM"><br><br>
      <label>Город рождения:</label><br>
      <input type="text" id="cityInput" name="city" value="{{ city or '' }}" placeholder="Начни вводить город..." autocomplete="off">
      <ul id="suggestions"></ul><br>
      <button type="submit">Рассчитать гороскоп</button>
    </form>

    {% if result_text %}
    <div class="result-container">
      <pre>{{ result_text }}</pre>
      {% if houses %}
      <div>
        <h3>🗺️ Североиндийская рашичакра</h3>
          <svg width="400" height="400" viewBox="0 0 400 400">
            <rect x="0" y="0" width="400" height="400" fill="none" stroke="#0033cc" stroke-width="2"/>
            <line x1="200" y1="0" x2="400" y2="200" stroke="#0033cc" stroke-width="2"/>
            <line x1="400" y1="200" x2="200" y2="400" stroke="#0033cc" stroke-width="2"/>
            <line x1="200" y1="400" x2="0" y2="200" stroke="#0033cc" stroke-width="2"/>
            <line x1="0" y1="200" x2="200" y2="0" stroke="#0033cc" stroke-width="2"/>
            <line x1="0" y1="0" x2="200" y2="200" stroke="#0033cc" stroke-width="2"/>
            <line x1="400" y1="0" x2="200" y2="200" stroke="#0033cc" stroke-width="2"/>
            <line x1="400" y1="400" x2="200" y2="200" stroke="#0033cc" stroke-width="2"/>
            <line x1="0" y1="400" x2="200" y2="200" stroke="#0033cc" stroke-width="2"/>

            <!-- Номера домов -->
            {% set house_coords = [(195,190),(95,90),(80,105),(180,205),(80,305),(95,320),
                                  (195,220),(295,320),(310,305),(210,205),(310,105),(290,90)] %}
            {% for coord in house_coords %}
              <text x="{{ coord[0] }}" y="{{ coord[1] }}">{{ houses[loop.index0] }}</text>
            {% endfor %}

            <!-- Планеты и градусы -->
            {% set centers = [(200,100),(100,40),(40,100),(100,200),(40,300),(100,360),
                              (200,300),(300,360),(360,300),(300,200),(360,100),(300,40)] %}
            {% for idx in range(12) %}
              {% set x, y = centers[idx] %}
              {% set planets_in_house = planets | selectattr('0', 'equalto', idx) | sort(attribute='2') | list %}
              {% if planets_in_house %}
                {% set total = planets_in_house | length %}
                {% set gap = 25 %}
                {% set start_x = x - (gap * (total-1) / 2) %}
                {% for p in planets_in_house %}
                  <text x="{{ start_x + loop.index0 * gap }}" y="{{ y }}" text-anchor="middle">{{ p[1] }}</text>
                  <text x="{{ start_x + loop.index0 * gap }}" y="{{ y + 12 }}" text-anchor="middle" style="font-size:10px;">{{ p[2] }}</text>
                {% endfor %}
              {% endif %}
            {% endfor %}
          </svg>

      </div>
      {% endif %}
    </div>
    {% endif %}
  </div>

<script>
function attachHandlers() {
  const cityInput = document.getElementById('cityInput');
  const suggestions = document.getElementById('suggestions');
  cityInput.addEventListener('input', () => {
    const query = cityInput.value.trim();
    if (query.length < 1) { suggestions.innerHTML = ''; return; }
    fetch(`/autocomplete?q=${query}`)
      .then(res => res.json())
      .then(data => {
        suggestions.innerHTML = '';
        data.forEach(city => {
          const li = document.createElement('li');
          li.textContent = city;
          li.onclick = () => { cityInput.value = city; suggestions.innerHTML = ''; };
          suggestions.appendChild(li);
        });
      });
  });
  const form = document.getElementById('form');
  form.addEventListener('submit', (e) => {
    e.preventDefault();
    const payload = {
      name: document.getElementById('nameInput').value,
      date: document.getElementById('dateInput').value,
      time: document.getElementById('timeInput').value,
      city: document.getElementById('cityInput').value
    };
    fetch('/calculate', {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(payload)
    })
    .then(res => res.text())
    .then(data => { document.getElementById('form-container').innerHTML = data; attachHandlers(); });
  });
}
attachHandlers();
</script>
</body>
</html>
"""

# ========================================
# ✅ Вспомогательные функции
# ========================================
def fix_date_format(date_str):
    cleaned = date_str.replace("-", "").replace(".", "").replace("/", "").replace(" ", "")
    if len(cleaned) == 8 and cleaned.isdigit():
        return f"{cleaned[:2]}-{cleaned[2:4]}-{cleaned[4:]}"
    return date_str

def fix_time_format(time_str):
    cleaned = time_str.replace(":", "").replace(".", "").replace(" ", "")
    if len(cleaned) == 3: cleaned = "0" + cleaned
    if len(cleaned) == 4 and cleaned.isdigit():
        return f"{cleaned[:2]}:{cleaned[2:]}"
    return time_str

def get_timezone(lat, lon):
    return tf.timezone_at(lat=lat, lng=lon)

def zodiac_position(degree):
    signs = ["Aries","Taurus","Gemini","Cancer","Leo","Virgo",
             "Libra","Scorpio","Sagittarius","Capricorn","Aquarius","Pisces"]
    sign = floor(degree / 30)
    pos_in_sign = degree % 30
    return signs[sign], pos_in_sign, sign + 1

def dms(degree_float):
    deg = int(degree_float)
    minutes_full = (degree_float - deg) * 60
    minutes = int(minutes_full)
    seconds = round((minutes_full - minutes) * 60)
    return f"{deg}° {minutes:02d}′ {seconds:02d}″"

def find_best_city(user_input):
    if not user_input: return None
    clean_city = user_input.split(",")[0].strip()
    matches = cities_df[cities_df["city"].str.lower().str.startswith(clean_city.lower())]
    if matches.empty: return None
    best = matches.iloc[0]
    return f"{best['city']}, {best['country']}", best["lat"], best["lng"]

# ========================================
# ✅ Flask endpoints
# ========================================
@app.route("/")
def index():
    return render_template_string(HTML_TEMPLATE, name='', date='', time='', city='', result_text=None, houses=None, planets=None)

@app.route("/autocomplete")
def autocomplete():
    q = request.args.get('q', '').lower()
    matches = cities_df[cities_df['city'].str.lower().str.startswith(q)]
    results = (matches['city'] + ', ' + matches['country']).head(10).tolist()
    return jsonify(results)

@app.route("/calculate", methods=["POST"])
def calculate():
    data = request.json
    name = data.get("name")
    birth_date_input = fix_date_format(data.get("date"))
    birth_time_input = fix_time_format(data.get("time"))
    city_input = data.get("city")

    try:
        birth_date = datetime.datetime.strptime(birth_date_input, "%d-%m-%Y").date()
        birth_time = datetime.datetime.strptime(birth_time_input, "%H:%M").time()
    except Exception:
        return "❌ Формат даты или времени неверный."

    best_city = find_best_city(city_input)
    if not best_city:
        return f"❌ Город [{city_input}] не найден."

    city_display, city_lat, city_lon = best_city
    tz_name = get_timezone(city_lat, city_lon)
    tz = pytz.timezone(tz_name)
    dt_naive = datetime.datetime.combine(birth_date, birth_time)
    local_dt = tz.localize(dt_naive, is_dst=None)
    offset_hours = local_dt.utcoffset().total_seconds() / 3600
    utc_dt = local_dt.astimezone(pytz.utc)
    jd = swe.julday(utc_dt.year, utc_dt.month, utc_dt.day, utc_dt.hour + utc_dt.minute / 60)
    ayanamsa = swe.get_ayanamsa(jd)
    cusps, ascmc = swe.houses(jd, city_lat, city_lon, b'E')
    asc_sidereal = (ascmc[0] - ayanamsa) % 360
    asc_sign, asc_deg, asc_sign_number = zodiac_position(asc_sidereal)
    houses = [((asc_sign_number + i - 1) % 12) + 1 for i in range(12)]

    result = [f"Имя: {name}",
              f"Город: {city_display}",
              f"Время: {local_dt.strftime('%Y-%m-%d %H:%M')} ({tz_name})",
              f"UTC offset: {offset_hours:+.0f}",
              f"Лагна: {asc_sign} {dms(asc_deg)}",
              f"Планеты:"]

    PLANETS = {"Sun": swe.SUN, "Moon": swe.MOON, "Mars": swe.MARS, "Mercury": swe.MERCURY,
               "Jupiter": swe.JUPITER, "Venus": swe.VENUS, "Saturn": swe.SATURN,
               "Rahu (True)": swe.TRUE_NODE, "Ketu (True)": swe.TRUE_NODE}
    PLANET_ABBR = {"Sun":"Su", "Moon":"Mo","Mars":"Ma","Mercury":"Me","Jupiter":"Ju",
                   "Venus":"Ve","Saturn":"Sa","Rahu (True)":"Ra","Ketu (True)":"Ke"}

    PLANET_POSITIONS = []
    PLANET_POSITIONS.append((0, 'As', int(asc_deg)))
    for p_name, p_val in PLANETS.items():
        pos, _ = swe.calc_ut(jd, p_val, swe.FLG_SIDEREAL)
        deg = (pos[0] + 180) % 360 if p_name == "Ketu (True)" else pos[0]
        sign, deg_in_sign, planet_sign_number = zodiac_position(deg)
        house_index = (planet_sign_number - asc_sign_number) % 12
        PLANET_POSITIONS.append((house_index, PLANET_ABBR[p_name], int(deg_in_sign)))
        result.append(f"{p_name:13}: {sign} {dms(deg_in_sign)} → Дом {house_index+1}")

    return render_template_string(HTML_TEMPLATE,
                                  result_text="\n".join(result),
                                  houses=houses,
                                  planets=PLANET_POSITIONS,
                                  name=name, date=data.get("date"), time=data.get("time"), city=city_input)

# ========================================
# ✅ Запуск локально
# ========================================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
