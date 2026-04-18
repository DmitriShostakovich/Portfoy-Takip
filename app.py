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
    pd.DataFrame(columns=['hisse_kodu','adet','tur','birim_fiyat','alis_fiyati']).to_csv(PORTFOY_DOSYASI, sep=';', index=False)
else:
    _df_kontrol = pd.read_csv(PORTFOY_DOSYASI, sep=';')
    if 'alis_fiyati' not in _df_kontrol.columns:
        _df_kontrol['alis_fiyati'] = 0.0
        _df_kontrol.to_csv(PORTFOY_DOSYASI, sep=';', index=False)

if not os.path.exists(GECMIS_DOSYASI):
    pd.DataFrame(columns=['tarih','toplam_tl','toplam_usd']).to_csv(GECMIS_DOSYASI, sep=';', index=False)

st.markdown("""<style>
.stApp { background-color: #0e1117; color: white; }
.ai-card { background-color: #1e2130; padding: 15px; border-radius: 10px;
           border-left: 5px solid #00ffcc; margin-bottom: 10px; }
</style>""", unsafe_allow_html=True)

# --- 2. ÇEKİRDEK FONKSİYONLAR ---

def safe_float(value, default=0.0):
    result = pd.to_numeric(value, errors='coerce')
    return float(result) if pd.notna(result) else default

def alis_para_birimi(tur):
    # Maden maliyeti artık TL. Sadece ABD ve Kripto USD kaldı.
    if tur in ['ABD', 'Kripto']: return 'USD'
    return 'TL'

def alis_fiyati_tl(alis_fiyati, tur, kur):
    # Sadece ABD ve Kripto maliyetleri kurla çarpılır
    if tur in ['ABD', 'Kripto']:
        return alis_fiyati * kur
    return alis_fiyati

def gecmis_kaydet(toplam_tl, effective_kur):
    bugun = datetime.now().strftime("%Y-%m-%d")
    if toplam_tl <= 0: return
    gecmis_df = pd.read_csv(GECMIS_DOSYASI, sep=';').dropna()
    if bugun not in gecmis_df['tarih'].values:
        yeni = pd.DataFrame([[bugun, toplam_tl, round(toplam_tl / effective_kur, 2)]],
                            columns=['tarih', 'toplam_tl', 'toplam_usd'])
        pd.concat([gecmis_df, yeni], ignore_index=True).to_csv(GECMIS_DOSYASI, sep=';', index=False)
    else:
        idx = gecmis_df[gecmis_df['tarih'] == bugun].index[0]
        gecmis_df.at[idx, 'toplam_tl'] = toplam_tl
        gecmis_df.at[idx, 'toplam_usd'] = round(toplam_tl / effective_kur, 2)
        gecmis_df.to_csv(GECMIS_DOSYASI, sep=';', index=False)

@st.cache_data(ttl=300, show_spinner="Piyasa verileri yükleniyor...")
def verileri_getir():
    df = pd.read_csv(PORTFOY_DOSYASI, sep=';').dropna(subset=['hisse_kodu'])
    if df.empty: return df, 1.0

    df.columns = df.columns.str.strip().str.lower()
    df['adet'] = pd.to_numeric(df['adet'], errors='coerce').fillna(0)
    df['birim_fiyat'] = pd.to_numeric(df['birim_fiyat'], errors='coerce').fillna(0)
    df['alis_fiyati'] = pd.to_numeric(df['alis_fiyati'], errors='coerce').fillna(0)

    tur_normalize = {"maden":"Maden","bist":"BIST","abd":"ABD","fon":"Fon","kripto":"Kripto","doviz":"Döviz","diger":"Diğer"}
    df['tur'] = df['tur'].map(lambda x: tur_normalize.get(str(x).lower().strip(), x))

    try:
        usd_kur = yf.Ticker("USDTRY=X").history(period="1d")['Close'].iloc[-1]
    except:
        usd_kur = 32.50 # Yedek kur

    effective_kur = usd_kur if usd_kur else 1.0
    tefas = Crawler()
    bas_tar = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
    bit_tar = datetime.now().strftime('%Y-%m-%d')

    fiyatlar, isimler = [], []
    for _, row in df.iterrows():
        kod, tur = str(row['hisse_kodu']).upper(), str(row['tur'])
        try:
            if tur == 'Diğer': 
                # Diğer kategorisinde birim fiyat 1 kabul edilir, adet değerdir.
                f, n = 1.0, kod
            elif tur == 'Fon':
                fv = tefas.fetch(start=bas_tar, end=bit_tar, name=kod)
                f, n = (fv['price'].iloc[-1], fv['title'].iloc[-1]) if not fv.empty else (0, kod)
            elif tur == 'Döviz':
                tick = yf.Ticker(f"{kod}TRY=X")
                f, n = tick.history(period="5d")['Close'].iloc[-1], tick.info.get('shortName', kod)
            elif tur == 'Maden':
                m_map = {"ALTIN": "GC=F", "GUMUS": "SI=F", "PLATIN": "PL=F", "PALADYUM": "PA=F"}
                ykod = m_map.get(kod, "GC=F")
                f = (yf.Ticker(ykod).history(period="5d")['Close'].iloc[-1] / 31.1035) * effective_kur
                n = f"Gram {kod.capitalize()}"
            elif tur == 'ABD':
                f = yf.Ticker(kod).history(period="5d")['Close'].iloc[-1] * effective_kur
                n = kod
            elif tur == 'Kripto':
                f = yf.Ticker(f"{kod}-USD").history(period="5d")['Close'].iloc[-1] * effective_kur
                n = kod
            elif tur == 'BIST':
                ykod = f"{kod}.IS" if not kod.endswith(".IS") else kod
                tick = yf.Ticker(ykod)
                f, n = tick.history(period="5d")['Close'].iloc[-1], tick.info.get('shortName', kod)
            else: f, n = 0, kod
            fiyatlar.append(f); isimler.append(n)
        except: fiyatlar.append(0); isimler.append(kod)

    df['Varlık İsmi'], df['birim_fiyat'] = isimler, fiyatlar
    
    # Değer hesaplama: Diğer kategorisi için Adet doğrudan TL değerdir
    df['Toplam Değer (TL)'] = df.apply(lambda r: float(r['adet']) if r['tur'] == 'Diğer' else float(r['adet']) * float(r['birim_fiyat']), axis=1)
    df['Toplam Değer (USD)'] = df['Toplam Değer (TL)'] / effective_kur
    
    # Maliyet hesaplama: Diğer kategorisinde alış fiyatı girildiyse o da doğrudan TL'dir
    df['Maliyet (TL)'] = df.apply(lambda r: (float(r['adet']) * alis_fiyati_tl(float(r['alis_fiyati']), r['tur'], effective_kur)) if r['tur'] not in ['Diğer'] else float(r['alis_fiyati']), axis=1)
    
    df['Kar/Zarar (TL)'] = df['Toplam Değer (TL)'] - df['Maliyet (TL)']
    df['Kar/Zarar (%)'] = df.apply(lambda r: (r['Kar/Zarar (TL)'] / r['Maliyet (TL)'] * 100) if r['Maliyet (TL)'] > 0 else 0, axis=1)
    df['Maliyet (USD)'] = df['Maliyet (TL)'] / effective_kur
    df['Kar/Zarar (USD)'] = df['Kar/Zarar (TL)'] / effective_kur

    return df.rename(columns={'hisse_kodu': 'Kod', 'adet': 'Adet'}), usd_kur

@st.cache_data(ttl=300, show_spinner=False)
def teknik_analiz(kod, tur):
    ykod = kod
    if kod in ["BTC", "ETH", "SOL"]: ykod = f"{kod}-USD"
    elif kod in ["ALTIN", "GUMUS", "PLATIN", "PALADYUM"]:
        ykod = {"ALTIN": "GC=F", "GUMUS": "SI=F", "PLATIN": "PL=F", "PALADYUM": "PA=F"}[kod]
    elif tur == "BIST": ykod = f"{kod}.IS"
    elif tur == "Döviz": ykod = f"{kod}TRY=X"
    try:
        hist = yf.Ticker(ykod).history(period="6mo")
        if len(hist) < 26: return None
        close = hist["Close"]
        delta = close.diff()
        rsi = 100 - (100 / (1 + (delta.where(delta > 0, 0).rolling(14).mean() / -delta.where(delta < 0, 0).rolling(14).mean().replace(0, 1e-10))))
        ema12, ema26 = close.ewm(span=12).mean(), close.ewm(span=26).mean()
        macd = (ema12 - ema26).iloc[-1]
        bb_mid, bb_std = close.rolling(20).mean(), close.rolling(20).std()
        bb_poz = (close.iloc[-1] - (bb_mid - 2 * bb_std).iloc[-1]) / (4 * bb_std.iloc[-1] + 1e-10)
        risk = int(abs(rsi.iloc[-1] - 50) * 2)
        puan = (1 if rsi.iloc[-1] < 40 else -1 if rsi.iloc[-1] > 70 else 0) + (1 if macd > 0 else -1)
        karar = "🟢 ALIM" if puan > 0 else "🔴 SATIM" if puan < 0 else "🟡 TUT"
        return {"karar": karar, "karar_renk": "#00c896" if "ALIM" in karar else "#ff4b4b" if "SATIM" in karar else "#ffd700",
                "rsi": round(rsi.iloc[-1], 1), "macd_karar": "📈 Yükseliş" if macd > 0 else "📉 Düşüş", "bb_poz": round(bb_poz * 100, 1), "risk": risk}
    except: return None

# --- 3. ARAYÜZ ---
with st.sidebar:
    st.title("💰 Akıllı Portföy")
    sayfa = st.radio("Menü", ["Portföyü İzle", "Kar / Zarar Analizi", "Pasta Grafik (Dağılım)", "YZ Danışmanı", "Varlık Grafikleri", "Gelişim Grafiği", "Varlık Yönetimi"])
    st.divider()
    st.caption("Para Birimi")
    c_tl, c_usd = st.columns(2)
    if c_tl.button("🇹🇷 TL", use_container_width=True, type="primary" if st.session_state["para_birimi"] == "TL" else "secondary"): st.session_state["para_birimi"] = "TL"; st.rerun()
    if c_usd.button("🇺🇸 USD", use_container_width=True, type="primary" if st.session_state["para_birimi"] == "USD" else "secondary"): st.session_state["para_birimi"] = "USD"; st.rerun()
    st.divider()
    if st.button("🔄 Piyasayı Güncelle"): verileri_getir.clear(); teknik_analiz.clear(); st.rerun()

data, usd_kur = verileri_getir()
if not data.empty and usd_kur: gecmis_kaydet(round(data["Toplam Değer (TL)"].sum(), 2), usd_kur)
pb = st.session_state["para_birimi"]
dg_s, kz_s, m_s, smb = ("Toplam Değer (TL)", "Kar/Zarar (TL)", "Maliyet (TL)", "₺") if pb == "TL" else ("Toplam Değer (USD)", "Kar/Zarar (USD)", "Maliyet (USD)", "$")

if sayfa == "Portföyü İzle":
    st.header("Anlık Portföy Durumu")
    if not data.empty:
        c1, c2, c3 = st.columns(3)
        c1.metric("Toplam Değer (TL)", f"₺{data['Toplam Değer (TL)'].sum():,.2f}")
        c2.metric("Toplam Değer (USD)", f"${data['Toplam Değer (USD)'].sum():,.2f}")
        c3.metric("Kur", f"₺{usd_kur:,.2f}")
        for t in ["Maden", "BIST", "ABD", "Fon", "Kripto", "Döviz", "Diğer"]:
            sub = data[data['tur'] == t]
            if not sub.empty:
                st.subheader(f"{t} — {smb}{sub[dg_s].sum():,.2f}")
                st.dataframe(sub[['Varlık İsmi', 'Kod', 'Adet', 'Toplam Değer (TL)', 'Toplam Değer (USD)']], use_container_width=True, hide_index=True)
    else: st.info("Portföy boş.")

elif sayfa == "Kar / Zarar Analizi":
    st.header("📈 Kar / Zarar Analizi")
    if not data.empty:
        kz_data = data[data['Maliyet (TL)'] > 0]
        c1, c2, c3 = st.columns(3)
        c1.metric("Toplam Maliyet", f"{smb}{kz_data[m_s].sum():,.2f}")
        c2.metric("Güncel Değer", f"{smb}{kz_data[dg_s].sum():,.2f}")
        c3.metric("K/Z", f"{smb}{kz_data[kz_s].sum():,.2f}", delta=f"%{kz_data[kz_s].sum()/(kz_data[m_s].sum() or 1)*100:+.2f}")
        for _, r in kz_data.iterrows():
            clr = "#00c896" if r[kz_s] >= 0 else "#ff4b4b"
            st.markdown(f"""<div style="background:#1e2130; border-radius:10px; padding:15px; border-left:5px solid {clr}; margin-bottom:10px;">
                <div style="display:flex; justify-content:space-between;"><b>{r['Varlık İsmi']} ({r['Kod']})</b> <span style="color:{clr}">{'▲' if r[kz_s]>=0 else '▼'} %{r['Kar/Zarar (%)']:,.2f}</span></div>
                <div style="display:grid; grid-template-columns: repeat(3, 1fr); gap:10px; margin-top:10px; font-size:0.85rem;">
                <div>Maliyet: {smb}{r[m_s]:,.2f}</div><div>Güncel: {smb}{r[dg_s]:,.2f}</div><div style="color:{clr}">K/Z: {smb}{r[kz_s]:,.2f}</div>
                </div></div>""", unsafe_allow_html=True)

elif sayfa == "Pasta Grafik (Dağılım)":
    st.header("📊 Dağılım Analizi")
    if not data.empty:
        fig, ax = plt.subplots(figsize=(6,6)); fig.patch.set_facecolor('#0e1117'); ax.set_facecolor('#0e1117')
        ax.pie(data[dg_s], labels=data['Kod'], autopct='%1.1f%%', textprops={'color':"w"}, wedgeprops={'edgecolor':'#0e1117'})
        st.pyplot(fig)

elif sayfa == "YZ Danışmanı":
    st.header("🤖 YZ Yatırım Asistanı")
    for _, r in data[~data['tur'].isin(['Diğer','Fon'])].iterrows():
        res = teknik_analiz(r['Kod'], r['tur'])
        if res:
            st.markdown(f"""<div style="background:#1e2130; padding:20px; border-radius:12px; border-left:5px solid {res['karar_renk']}; margin-bottom:15px;">
                <h4 style="margin:0;">{r['Varlık İsmi']} -> {res['karar']}</h4>
                <div style="display:grid; grid-template-columns:repeat(3,1fr); margin-top:10px;">
                <div>RSI: {res['rsi']}</div><div>MACD: {res['macd_karar']}</div><div>Risk: {res['risk']}/100</div>
                </div></div>""", unsafe_allow_html=True)

elif sayfa == "Varlık Grafikleri":
    st.header("📈 Canlı Grafikler")
    if not data.empty:
        sel = st.selectbox("Varlık Seçin", data['Kod'].unique())
        r = data[data['Kod'] == sel].iloc[0]
        ykod = sel
        if sel in ["BTC", "ETH", "SOL"]: ykod = f"{sel}-USD"
        elif sel == "ALTIN": ykod = "GC=F"
        elif sel == "GUMUS": ykod = "SI=F"
        elif r['tur'] == 'BIST': ykod = f"{sel}.IS"
        st.line_chart(yf.Ticker(ykod).history(period="1mo")['Close'])

elif sayfa == "Gelişim Grafiği":
    st.header("📉 Portföy Gelişimi")
    gecmis = pd.read_csv(GECMIS_DOSYASI, sep=';')
    if not gecmis.empty: st.line_chart(gecmis.set_index('tarih')['toplam_tl' if pb=="TL" else 'toplam_usd'])

elif sayfa == "Varlık Yönetimi":
    st.header("Varlık Yönetimi")
    with st.form("yeni_ekle"):
        c1, c2, c3, c4 = st.columns(4)
        k, t = c1.text_input("Kod").upper().strip(), c2.selectbox("Tür", ["Maden","BIST","ABD","Fon","Kripto","Döviz","Diğer"])
        v_help = "Varlığın TL değeri" if t == "Diğer" else "Varlık miktarı"
        a_help = "Toplam TL maliyet" if t == "Diğer" else f"Birim maliyet ({alis_para_birimi(t)})"
        
        v, a = c3.number_input("Miktar / Değer", min_value=0.0, format="%.4f", help=v_help), c4.number_input(f"Maliyet ({alis_para_birimi(t)})", min_value=0.0, format="%.4f", help=a_help)
        if st.form_submit_button("Ekle"):
            df_m = pd.read_csv(PORTFOY_DOSYASI, sep=';')
            df_m = pd.concat([df_m, pd.DataFrame([[k, v, t, 0.0, a]], columns=df_m.columns)])
            df_m.to_csv(PORTFOY_DOSYASI, sep=';', index=False); verileri_getir.clear(); st.rerun()
    st.divider()
    df_m = pd.read_csv(PORTFOY_DOSYASI, sep=';')
    for i, r in df_m.iterrows():
        c1, c2, c3, c4, c5 = st.columns([2,2,2,1,1])
        c1.write(f"**{r['hisse_kodu']}** ({r['tur']})")
        nv = c2.number_input("Mik/Değer", value=float(r['adet']), key=f"v{i}", format="%.4f")
        na = c3.number_input(f"Mal({alis_para_birimi(r['tur'])})", value=float(r['alis_fiyati']), key=f"a{i}", format="%.4f")
        if c4.button("🔄", key=f"u{i}"):
            df_m.at[i, 'adet'], df_m.at[i, 'alis_fiyati'] = nv, na
            df_m.to_csv(PORTFOY_DOSYASI, sep=';', index=False); verileri_getir.clear(); st.rerun()
        if c5.button("🗑️", key=f"d{i}"):
            df_m.drop(i).to_csv(PORTFOY_DOSYASI, sep=';', index=False); verileri_getir.clear(); st.rerun()
