import streamlit as st
import pandas as pd
import yfinance as yf
from tefas import Crawler
from datetime import datetime, timedelta
import matplotlib.pyplot as plt
import os

# --- 1. AYARLAR VE DOSYA HAZIRLIĞI ---
st.set_page_config(page_title="Akıllı Portföyüm", layout="wide")

if "para_birimi" not in st.session_state:
    st.session_state["para_birimi"] = "TL"

PORTFOY_DOSYASI = "portfoy_verileri.csv"
GECMIS_DOSYASI  = "gelisim_gecmisi.csv"

if not os.path.exists(PORTFOY_DOSYASI):
    pd.DataFrame(columns=['hisse_kodu','adet','tur','birim_fiyat']).to_csv(PORTFOY_DOSYASI, sep=';', index=False)
if not os.path.exists(GECMIS_DOSYASI):
    pd.DataFrame(columns=['tarih','toplam_tl','toplam_usd']).to_csv(GECMIS_DOSYASI, sep=';', index=False)

st.markdown("""<style>
.stApp { background-color: #0e1117; color: white; }
.ai-card { background-color: #1e2130; padding: 15px; border-radius: 10px;
           border-left: 5px solid #00ffcc; margin-bottom: 10px; }
</style>""", unsafe_allow_html=True)

# --- 2. ÇEKİRDEK FONKSİYONLAR ---

# TTL=300 → 5 dakika cache, "Piyasayı Güncelle" butonu cache'i sıfırlar
@st.cache_data(ttl=300, show_spinner="Piyasa verileri yükleniyor...")
def verileri_getir():
    df = pd.read_csv(PORTFOY_DOSYASI, sep=';').dropna(subset=['hisse_kodu'])
    if df.empty:
        return df, 1.0

    df.columns = df.columns.str.strip().str.lower()
    # Eski küçük harf tur değerlerini yeni formata normalize et
    tur_normalize = {"maden":"Maden","bist":"BIST","abd":"ABD","fon":"Fon",
                     "kripto":"Kripto","doviz":"Döviz","diger":"Diğer"}
    df['tur'] = df['tur'].map(lambda x: tur_normalize.get(str(x).lower().strip(), x))
    tefas = Crawler()
    bas_tar = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
    bit_tar = datetime.now().strftime('%Y-%m-%d')

    try:
        usd_kur = yf.Ticker("USDTRY=X").history(period="1d")['Close'].iloc[-1]
    except:
        usd_kur = 1.0

    fiyatlar, isimler = [], []
    for _, row in df.iterrows():
        kod, tur = str(row['hisse_kodu']).upper(), str(row['tur']).lower()
        try:
            if tur == 'Diğer':
                f, n = float(row['birim_fiyat']), kod
            elif tur == 'Fon':
                fv = tefas.fetch(start=bas_tar, end=bit_tar, name=kod)
                if not fv.empty: f, n = fv['price'].iloc[-1], fv['title'].iloc[-1]
                else: f, n = 0, kod
            else:
                ykod = kod
                if kod in ["BTC", "ETH", "SOL"]:
                    ykod, n = f"{kod}-USD", kod
                elif kod == "ALTIN":  ykod, n = "GC=F", "Gram Altın"
                elif kod == "GUMUS":  ykod, n = "SI=F", "Gram Gümüş"
                elif kod == "PLATIN": ykod, n = "PL=F", "Gram Platin"
                elif kod == "PALADYUM": ykod, n = "PA=F", "Gram Paladyum"
                else:
                    if tur == 'BIST' and not kod.endswith(".IS"): ykod = f"{kod}.IS"
                    elif tur == 'Döviz': ykod = f"{kod}TRY=X"
                    tick = yf.Ticker(ykod)
                    n = tick.info.get('shortName', kod)

                hist = yf.Ticker(ykod).history(period="5d")
                f = hist['Close'].iloc[-1] if not hist.empty else 0

                if tur in ['ABD', 'Kripto'] or (tur == 'doviz' and kod != 'USD'):
                    if tur != 'Döviz': f *= usd_kur
                if kod in ["ALTIN", "GUMUS", "PLATIN", "PALADYUM"]:
                    f = (f / 31.1035) * usd_kur

            fiyatlar.append(f); isimler.append(n)
        except:
            fiyatlar.append(0); isimler.append(kod)

    df['Varlık İsmi']   = isimler
    df['birim_fiyat']   = fiyatlar
    df['Toplam Değer']  = df.apply(
        lambda r: r['birim_fiyat'] if r['tur'] == 'Diğer' else r['adet'] * r['birim_fiyat'], axis=1
    )

    # Geçmiş kayıt
    toplam_tl = round(df['Toplam Değer'].sum(), 2)
    bugun = datetime.now().strftime("%Y-%m-%d")
    if toplam_tl > 0:
        gecmis_df = pd.read_csv(GECMIS_DOSYASI, sep=';').dropna()
        if bugun not in gecmis_df['tarih'].values:
            yeni = pd.DataFrame([[bugun, toplam_tl, round(toplam_tl / usd_kur, 2)]],
                                columns=['tarih', 'toplam_tl', 'toplam_usd'])
            pd.concat([gecmis_df, yeni], ignore_index=True).to_csv(GECMIS_DOSYASI, sep=';', index=False)
        else:
            idx = gecmis_df[gecmis_df['tarih'] == bugun].index[0]
            gecmis_df.at[idx, 'toplam_tl'] = toplam_tl
            gecmis_df.to_csv(GECMIS_DOSYASI, sep=';', index=False)

    return df.rename(columns={'hisse_kodu': 'Kod', 'adet': 'Adet'}), usd_kur


@st.cache_data(ttl=300, show_spinner=False)
def ai_analiz(kod, tur):
    """
    Teknik göstergeler hesaplar ve detaylı rapor dict döndürür:
    - RSI (14): Aşım tespiti
    - MACD: Momentum yönü
    - Bollinger Bantları: Volatilite ve fiyat konumu
    - Fiyat değişimi (1g, 1h, 3a)
    - Hacim ortalaması
    - Risk skoru (0-100)
    """
    ykod = kod
    if kod in ["BTC", "ETH", "SOL"]: ykod = f"{kod}-USD"
    elif kod in ["ALTIN", "GUMUS", "PLATIN", "PALADYUM"]:
        ykod = {"ALTIN": "GC=F", "GUMUS": "SI=F", "PLATIN": "PL=F", "PALADYUM": "PA=F"}[kod]
    elif tur == "BIST":  ykod = f"{kod}.IS"
    elif tur == "Döviz": ykod = f"{kod}TRY=X"

    try:
        hist = yf.Ticker(ykod).history(period="6mo")
    except:
        return None

    if len(hist) < 26:
        return None

    close = hist["Close"]
    volume = hist["Volume"]

    # --- RSI (14) ---
    delta = close.diff()
    gain = delta.where(delta > 0, 0).rolling(14).mean()
    loss = -delta.where(delta < 0, 0).rolling(14).mean()
    rs = gain / loss.replace(0, 1e-10)
    rsi = float((100 - 100 / (1 + rs)).iloc[-1])

    # --- MACD (12, 26, 9) ---
    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()
    macd_line   = ema12 - ema26
    signal_line = macd_line.ewm(span=9, adjust=False).mean()
    macd_hist   = float((macd_line - signal_line).iloc[-1])
    macd_val    = float(macd_line.iloc[-1])
    signal_val  = float(signal_line.iloc[-1])

    # --- Bollinger Bantları (20, 2σ) ---
    sma20  = close.rolling(20).mean()
    std20  = close.rolling(20).std()
    upper  = float((sma20 + 2 * std20).iloc[-1])
    lower  = float((sma20 - 2 * std20).iloc[-1])
    mid    = float(sma20.iloc[-1])
    fiyat  = float(close.iloc[-1])
    bb_poz = (fiyat - lower) / (upper - lower + 1e-10)  # 0=alt bant, 1=üst bant

    # --- Fiyat Değişimleri ---
    def degisim(n):
        if len(close) > n:
            return float((close.iloc[-1] - close.iloc[-n]) / close.iloc[-n] * 100)
        return None

    d1g = degisim(1)
    d1h = degisim(5)
    d3a = degisim(63)

    # --- Hacim ---
    avg_vol = float(volume.rolling(20).mean().iloc[-1]) if not volume.empty else 0
    son_vol = float(volume.iloc[-1]) if not volume.empty else 0
    vol_oran = (son_vol / avg_vol) if avg_vol > 0 else 1

    # --- Sinyal ---
    sinyaller = []
    puan = 0  # pozitif = alım yönlü

    if rsi < 30:   sinyaller.append("RSI aşırı satım"); puan += 2
    elif rsi < 40: sinyaller.append("RSI satım bölgesi"); puan += 1
    elif rsi > 70: sinyaller.append("RSI aşırı alım"); puan -= 2
    elif rsi > 60: sinyaller.append("RSI alım bölgesi"); puan -= 1

    if macd_hist > 0 and macd_val > signal_val:
        sinyaller.append("MACD yükseliş"); puan += 1
    elif macd_hist < 0 and macd_val < signal_val:
        sinyaller.append("MACD düşüş"); puan -= 1

    if bb_poz < 0.2:  sinyaller.append("Alt Bollinger bandı"); puan += 1
    elif bb_poz > 0.8: sinyaller.append("Üst Bollinger bandı"); puan -= 1

    if vol_oran > 1.5: sinyaller.append("Yüksek hacim")

    if puan >= 2:    karar, karar_renk = "🟢 ALIM FIRSATI", "#00c896"
    elif puan <= -2: karar, karar_renk = "🔴 SATIM ZAMANI", "#ff4b4b"
    else:            karar, karar_renk = "🟡 TUT",          "#ffd700"

    # --- Risk Skoru (0=düşük risk, 100=yüksek risk) ---
    volatilite = float(close.pct_change().rolling(20).std().iloc[-1] * 100)
    risk = min(100, int(
        (abs(rsi - 50) / 50 * 30) +       # RSI uç değerleri
        (min(volatilite, 5) / 5 * 40) +   # Volatilite
        (abs(bb_poz - 0.5) * 30)          # Bollinger konumu
    ))

    return {
        "karar": karar,
        "karar_renk": karar_renk,
        "rsi": round(rsi, 1),
        "macd_hist": round(macd_hist, 4),
        "macd_karar": "📈 Yükseliş" if macd_hist > 0 else "📉 Düşüş",
        "bb_poz": round(bb_poz * 100, 1),
        "fiyat": round(fiyat, 4),
        "d1g": round(d1g, 2) if d1g is not None else None,
        "d1h": round(d1h, 2) if d1h is not None else None,
        "d3a": round(d3a, 2) if d3a is not None else None,
        "vol_oran": round(vol_oran, 2),
        "risk": risk,
        "sinyaller": sinyaller,
        "bb_upper": round(upper, 4),
        "bb_lower": round(lower, 4),
        "bb_mid": round(mid, 4),
    }


@st.cache_data(ttl=300, show_spinner=False)
def grafik_verisi_getir(ykod):
    return yf.Ticker(ykod).history(period="1mo")


# --- 3. ARAYÜZ ---
with st.sidebar:
    st.title("💰 Akıllı Portföy")
    sayfa = st.radio("Menü", [
        "Portföyü İzle", "Pasta Grafik (Dağılım)",
        "YZ Danışmanı", "Varlık Grafikleri",
        "Gelişim Grafiği", "Varlık Yönetimi"
    ])
    st.divider()
    if st.button("🔄 Piyasayı Güncelle"):
        # Cache'i temizle ve yeniden yükle
        verileri_getir.clear()
        ai_analiz.clear()
        grafik_verisi_getir.clear()
        st.rerun()
    st.caption("Veriler 5 dakika önbellekte tutulur.")

data, usd_kur = verileri_getir()

# --- 4. SAYFALAR ---
if sayfa == "Portföyü İzle":
    st.header("Anlık Portföy Durumu")
    if not data.empty:
        birim = "$" if st.session_state["para_birimi"] == "USD" else "TL"
        st.metric("Toplam Değer", f"{data['Toplam Değer'].sum():,.2f} {birim}")
        for t in ["Maden", "BIST", "ABD", "Fon", "Kripto", "Döviz", "Diğer"]:
            subset = data[data['tur'] == t]
            if not subset.empty:
                st.subheader(t)
                st.dataframe(subset[['Varlık İsmi','Kod','Adet','Toplam Değer']],
                             use_container_width=True, hide_index=True)

elif sayfa == "Pasta Grafik (Dağılım)":
    st.header("📊 Varlık Dağılım Analizi")
    if not data.empty:
        st.subheader("Bireysel Varlık Dağılımı")
        fig1, ax1 = plt.subplots()
        ax1.pie(data['Toplam Değer'], labels=data['Kod'], autopct='%1.1f%%',
                startangle=90, textprops={'color': "white"})
        fig1.patch.set_alpha(0)
        st.pyplot(fig1)

        st.subheader("Varlık Sınıfı Dağılımı")
        tur_ozet = data.groupby('tur')['Toplam Değer'].sum()
        fig2, ax2 = plt.subplots()
        ax2.pie(tur_ozet, labels=tur_ozet.index, autopct='%1.1f%%',
                startangle=90, textprops={'color': "white"})
        fig2.patch.set_alpha(0)
        st.pyplot(fig2)
    else:
        st.warning("Gösterilecek veri bulunamadı.")

elif sayfa == "YZ Danışmanı":
    st.header("🤖 YZ Yatırım Asistanı")

    if data.empty:
        st.warning("Portföyde varlık bulunamadı.")
    else:
        analiz_data = data[~data["tur"].isin(["Diğer", "Fon"])]

        # --- Portföy Geneli Risk Skoru ---
        risk_skorlari = []
        for _, row in analiz_data.iterrows():
            r = ai_analiz(row["Kod"], row["tur"])
            if r: risk_skorlari.append(r["risk"])

        if risk_skorlari:
            ort_risk = int(sum(risk_skorlari) / len(risk_skorlari))
            if ort_risk < 33:   risk_label, risk_renk = "🟢 Düşük Risk", "#00c896"
            elif ort_risk < 66: risk_label, risk_renk = "🟡 Orta Risk",  "#ffd700"
            else:               risk_label, risk_renk = "🔴 Yüksek Risk","#ff4b4b"

            c1, c2, c3 = st.columns(3)
            c1.metric("Portföy Risk Skoru", f"{ort_risk}/100", risk_label)
            c2.metric("Analiz Edilen Varlık", len(risk_skorlari))
            c3.metric("Yüksek Riskli Varlık", sum(1 for r in risk_skorlari if r >= 66))
            st.divider()

        # --- Varlık Bazlı Detaylı Kartlar ---
        for _, row in analiz_data.iterrows():
            r = ai_analiz(row["Kod"], row["tur"])
            if r is None:
                st.warning(f"{row['Kod']}: Yetersiz veri")
                continue

            def renk(deger):
                if deger is None: return "gray"
                return "#00c896" if deger >= 0 else "#ff4b4b"

            def ok(deger):
                if deger is None: return "—"
                return f"▲ {deger:+.2f}%" if deger >= 0 else f"▼ {deger:+.2f}%"

            risk_bar = int(r["risk"] / 10)
            risk_dolu = "█" * risk_bar + "░" * (10 - risk_bar)

            sinyaller_html = " · ".join(r["sinyaller"]) if r["sinyaller"] else "Belirgin sinyal yok"

            st.markdown(f"""
<div style="background:#1e2130; border-radius:12px; padding:18px;
            border-left:5px solid {r["karar_renk"]}; margin-bottom:14px;">

  <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:12px;">
    <span style="font-size:1.1rem; font-weight:700;">{row["Varlık İsmi"]} <span style="color:#aaa; font-size:0.9rem;">({row["Kod"]})</span></span>
    <span style="background:{r["karar_renk"]}22; color:{r["karar_renk"]};
                 padding:4px 12px; border-radius:20px; font-weight:700; font-size:0.95rem;">
      {r["karar"]}
    </span>
  </div>

  <div style="display:grid; grid-template-columns:repeat(4,1fr); gap:10px; margin-bottom:12px;">
    <div style="background:#12151f; border-radius:8px; padding:10px; text-align:center;">
      <div style="color:#aaa; font-size:0.72rem; margin-bottom:4px;">RSI (14)</div>
      <div style="font-size:1.1rem; font-weight:700;
           color:{"#ff4b4b" if r["rsi"]>70 else "#00c896" if r["rsi"]<30 else "#ffd700"}">
        {r["rsi"]}
      </div>
    </div>
    <div style="background:#12151f; border-radius:8px; padding:10px; text-align:center;">
      <div style="color:#aaa; font-size:0.72rem; margin-bottom:4px;">MACD</div>
      <div style="font-size:0.95rem; font-weight:700;">{r["macd_karar"]}</div>
    </div>
    <div style="background:#12151f; border-radius:8px; padding:10px; text-align:center;">
      <div style="color:#aaa; font-size:0.72rem; margin-bottom:4px;">Bollinger %B</div>
      <div style="font-size:1.1rem; font-weight:700;
           color:{"#ff4b4b" if r["bb_poz"]>80 else "#00c896" if r["bb_poz"]<20 else "#ffd700"}">
        %{r["bb_poz"]}
      </div>
    </div>
    <div style="background:#12151f; border-radius:8px; padding:10px; text-align:center;">
      <div style="color:#aaa; font-size:0.72rem; margin-bottom:4px;">Hacim Oranı</div>
      <div style="font-size:1.1rem; font-weight:700;
           color:{"#00c896" if r["vol_oran"]>1.5 else "white"}">
        {r["vol_oran"]}x
      </div>
    </div>
  </div>

  <div style="display:grid; grid-template-columns:repeat(3,1fr); gap:10px; margin-bottom:12px;">
    <div style="background:#12151f; border-radius:8px; padding:10px; text-align:center;">
      <div style="color:#aaa; font-size:0.72rem; margin-bottom:4px;">Günlük</div>
      <div style="font-size:1rem; font-weight:700; color:{renk(r["d1g"])}">{ok(r["d1g"])}</div>
    </div>
    <div style="background:#12151f; border-radius:8px; padding:10px; text-align:center;">
      <div style="color:#aaa; font-size:0.72rem; margin-bottom:4px;">Haftalık</div>
      <div style="font-size:1rem; font-weight:700; color:{renk(r["d1h"])}">{ok(r["d1h"])}</div>
    </div>
    <div style="background:#12151f; border-radius:8px; padding:10px; text-align:center;">
      <div style="color:#aaa; font-size:0.72rem; margin-bottom:4px;">3 Aylık</div>
      <div style="font-size:1rem; font-weight:700; color:{renk(r["d3a"])}">{ok(r["d3a"])}</div>
    </div>
  </div>

  <div style="display:flex; justify-content:space-between; align-items:center;
              background:#12151f; border-radius:8px; padding:10px;">
    <div>
      <span style="color:#aaa; font-size:0.72rem;">Risk: </span>
      <span style="font-family:monospace; color:{"#ff4b4b" if r["risk"]>=66 else "#ffd700" if r["risk"]>=33 else "#00c896"}">
        {risk_dolu}
      </span>
      <span style="color:#aaa; font-size:0.8rem;"> {r["risk"]}/100</span>
    </div>
    <div style="color:#aaa; font-size:0.8rem;">💡 {sinyaller_html}</div>
  </div>

</div>
""", unsafe_allow_html=True)

elif sayfa == "Varlık Grafikleri":
    st.header("📈 Canlı Grafikler")
    if not data.empty:
        grafik_listesi = data[~data['tur'].isin(['Diğer', 'Fon'])]['Kod'].unique()
        secim = st.selectbox("Varlık Seçin", grafik_listesi)
        if secim:
            row = data[data['Kod'] == secim].iloc[0]
            ykod = secim
            if secim in ["BTC", "ETH", "SOL"]:   ykod = f"{secim}-USD"
            elif secim == "ALTIN":   ykod = "GC=F"
            elif secim == "GUMUS":   ykod = "SI=F"
            elif secim == "PLATIN":  ykod = "PL=F"
            elif secim == "PALADYUM": ykod = "PA=F"
            elif row['tur'] == 'BIST':  ykod = f"{secim}.IS"
            elif row['tur'] == 'Döviz': ykod = f"{secim}TRY=X"

            hist = grafik_verisi_getir(ykod)
            if not hist.empty:
                st.line_chart(hist['Close'])

elif sayfa == "Gelişim Grafiği":
    st.header("📉 Toplam Gelişim")
    gecmis = pd.read_csv(GECMIS_DOSYASI, sep=';')
    if not gecmis.empty:
        sutun = 'toplam_tl' if st.session_state["para_birimi"] == "TL" else 'toplam_usd'
        st.line_chart(gecmis.set_index('tarih')[sutun])

elif sayfa == "Varlık Yönetimi":
    st.header("Varlık Yönetimi")
    with st.form("ekle", clear_on_submit=True):
        c1, c2, c3 = st.columns(3)
        y_k = c1.text_input("Kod (Örn: THYAO, AUD, PLATIN)").upper().strip()
        y_t = c2.selectbox("Tür", ["Maden","BIST","ABD","Fon","Kripto","Döviz","Diğer"])
        y_v = c3.number_input("Miktar", format="%.4f")
        if st.form_submit_button("Ekle / Üzerine Ekle"):
            df_m = pd.read_csv(PORTFOY_DOSYASI, sep=';')
            if y_k in df_m['hisse_kodu'].values:
                df_m.loc[df_m['hisse_kodu'] == y_k,
                         'adet' if y_t != 'Diğer' else 'birim_fiyat'] += y_v
            else:
                yeni = pd.DataFrame(
                    [[y_k, y_v if y_t != 'Diğer' else 1.0, y_t, y_v if y_t == 'diger' else 0.0]],
                    columns=df_m.columns
                )
                df_m = pd.concat([df_m, yeni])
            df_m.to_csv(PORTFOY_DOSYASI, sep=';', index=False)
            verileri_getir.clear()  # Varlık eklendikten sonra cache sıfırla
            st.rerun()

    df_m = pd.read_csv(PORTFOY_DOSYASI, sep=';').dropna()
    for i, r in df_m.iterrows():
        c1, c2, c3, c4 = st.columns([2, 2, 1, 1])
        c1.write(f"**{r['hisse_kodu']}**")
        nv = c2.number_input("Miktar", value=float(r['adet'] if r['tur'] != 'Diğer' else r['birim_fiyat']), key=f"v_{i}")
        if c3.button("🔄", key=f"u_{i}"):
            df_m.at[i, 'adet' if r['tur'] != 'Diğer' else 'birim_fiyat'] = nv
            df_m.to_csv(PORTFOY_DOSYASI, sep=';', index=False)
            verileri_getir.clear()
            st.rerun()
        if c4.button("🗑️", key=f"d_{i}"):
            df_m.drop(i).to_csv(PORTFOY_DOSYASI, sep=';', index=False)
            verileri_getir.clear()
            st.rerun()
