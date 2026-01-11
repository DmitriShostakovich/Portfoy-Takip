import streamlit as st
import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta
import matplotlib.pyplot as plt
import os

# --- 1. OTURUM VE DOSYA HAZIRLIĞI ---
if "giris_yapildi" not in st.session_state:
    st.session_state["giris_yapildi"] = False
if "aktif_kullanici" not in st.session_state:
    st.session_state["aktif_kullanici"] = None
if "para_birimi" not in st.session_state:
    st.session_state["para_birimi"] = "TL"

# Kullanıcı veritabanı kontrolü
if not os.path.exists('kullanicilar.csv'):
    pd.DataFrame(columns=['kullanici_adi', 'sifre']).to_csv('kullanicilar.csv', sep=';', index=False)

# --- 2. GİRİŞ VE PROFİL SİSTEMİ ---
def giris_sistemi():
    st.markdown("<h1 style='text-align: center;'>🔐 Portföy Yönetim Sistemi</h1>", unsafe_allow_html=True)
    tab1, tab2 = st.tabs(["Giriş Yap", "Profil Oluştur"])
    
    with tab1:
        with st.form("giris_formu"):
            k_adi = st.text_input("Kullanıcı Adı").strip()
            sifre = st.text_input("Şifre", type="password").strip()
            submit = st.form_submit_button("Giriş Yap", use_container_width=True)
            if submit:
                df_k = pd.read_csv('kullanicilar.csv', sep=';', dtype=str).fillna("")
                user = df_k[(df_k['kullanici_adi'] == k_adi) & (df_k['sifre'] == sifre)]
                if not user.empty:
                    st.session_state["giris_yapildi"] = True
                    st.session_state["aktif_kullanici"] = k_adi
                    st.rerun()
                else:
                    st.error("Kullanıcı adı veya şifre hatalı!")

    with tab2:
        with st.form("profil_olustur_formu"):
            st.subheader("Yeni Profil Bilgileri")
            y_kadi = st.text_input("Yeni Kullanıcı Adı").strip()
            y_sifre = st.text_input("Yeni Şifre", type="password").strip()
            y_submit = st.form_submit_button("Profil Oluştur", use_container_width=True)
            if y_submit:
                df_k = pd.read_csv('kullanicilar.csv', sep=';', dtype=str).fillna("")
                if y_kadi in df_k['kullanici_adi'].values:
                    st.warning("Bu kullanıcı adı zaten alınmış!")
                elif y_kadi and y_sifre:
                    yeni_user = pd.DataFrame([[y_kadi, y_sifre]], columns=['kullanici_adi', 'sifre'])
                    pd.concat([df_k, yeni_user], ignore_index=True).to_csv('kullanicilar.csv', sep=';', index=False)
                    st.success("Profil başarıyla oluşturuldu! Şimdi giriş yapabilirsiniz.")
                else:
                    st.error("Lütfen tüm alanları doldurun!")

# --- 3. ANA UYGULAMA MANTIĞI ---
if not st.session_state["giris_yapildi"]:
    giris_sistemi()
else:
    # Her kullanıcı için ayrı dosya
    PORTFOY_DOSYASI = f"portfoy_{st.session_state['aktif_kullanici']}.csv"
    
    st.markdown("""<style>.stApp { background-color: #0e1117; color: white; } h1, h2, h3, p, span { color: white !important; } .footer-text { color: gray; font-size: 0.8rem; text-align: center; } .bilgi-notu { color: #888; font-size: 0.9rem; margin-top: 15px; } .uyari-notu { color: #ffcc00; font-size: 0.85rem; font-style: italic; }</style>""", unsafe_allow_html=True)

    def verileri_getir():
        if not os.path.exists(PORTFOY_DOSYASI):
            pd.DataFrame(columns=['hisse_kodu', 'adet', 'tur', 'birim_fiyat']).to_csv(PORTFOY_DOSYASI, sep=';', index=False)
            return pd.DataFrame()
        
        df = pd.read_csv(PORTFOY_DOSYASI, sep=';').dropna(subset=['hisse_kodu'])
        if df.empty: return df
        df.columns = df.columns.str.strip().str.lower()
        
        try: usd_kur = yf.Ticker("USDTRY=X").history(period="1d")['Close'].iloc[-1]
        except: usd_kur = 1
        
        fiyatlar, isimler = [], []
        for _, row in df.iterrows():
            kod, tur = str(row['hisse_kodu']).upper(), str(row['tur']).lower()
            try:
                if tur == 'diger': 
                    f, n = float(row['birim_fiyat']), kod
                else:
                    ykod = kod
                    if kod in ["BTC", "ETH", "SOL"]: 
                        ykod, n = f"{kod}-USD", {"BTC":"Bitcoin","ETH":"Ethereum","SOL":"Solana"}[kod]
                    elif kod == "ALTIN": ykod, n = "GC=F", "Gram Altın"
                    elif kod == "GUMUS": ykod, n = "SI=F", "Gram Gümüş"
                    else:
                        if tur == 'bist' and not kod.endswith(".IS"): ykod = f"{kod}.IS"
                        if tur == 'fon' and not kod.endswith(".IS"): ykod = f"{kod}.IS"
                        ykod = {"USD": "USDTRY=X", "EUR": "EURTRY=X"}.get(kod, ykod)
                        tick = yf.Ticker(ykod)
                        n = tick.info.get('shortName', kod)
                        if "Bitcoin USD" in n: n = "Bitcoin"
                    
                    hist = yf.Ticker(ykod).history(period="5d")
                    f = hist['Close'].iloc[-1] if not hist.empty else 0
                    if tur in ['abd', 'kripto']: f *= usd_kur
                    if kod in ["ALTIN", "GUMUS"]: f = (f / 31.1035) * usd_kur
                fiyatlar.append(f); isimler.append(n)
            except: 
                fiyatlar.append(0); isimler.append(kod)
            
        df['Varlık İsmi'], df['birim_fiyat'] = isimler, fiyatlar
        df['Toplam Değer'] = df.apply(lambda r: r['birim_fiyat'] if r['tur'] == 'diger' else r['adet'] * r['birim_fiyat'], axis=1)
        
        if st.session_state["para_birimi"] == "USD":
            df['Toplam Değer'] /= usd_kur
            df['birim_fiyat'] /= usd_kur
        return df.rename(columns={'hisse_kodu': 'Kod', 'adet': 'Adet'})

    # --- SIDEBAR ---
    with st.sidebar:
        st.title(f"👤 {st.session_state['aktif_kullanici']}")
        st.divider()
        sayfa = st.radio("Menü", ["Portföyü İzle", "Portföy Analizi", "Varlık Yönetimi"])
        st.divider()
        if st.button("🚪 Çıkış Yap", use_container_width=True):
            st.session_state["giris_yapildi"] = False
            st.session_state["aktif_kullanici"] = None
            st.rerun()

    # --- SAYFALAR ---
    if sayfa == "Portföyü İzle":
        c1, c2 = st.columns([3, 1])
        c1.header("Anlık Portföy Durumu")
        btn_label = "🇹🇷 TL Göster" if st.session_state["para_birimi"] == "USD" else "🇺🇸 USD Göster"
        if c2.button(btn_label, use_container_width=True):
            st.session_state["para_birimi"] = "USD" if st.session_state["para_birimi"] == "TL" else "TL"
            st.rerun()
        
        data = verileri_getir()
        if not data.empty:
            birim = "$" if st.session_state["para_birimi"] == "USD" else "TL"
            st.metric(f"Toplam Değer", f"{data['Toplam Değer'].sum():,.2f} {birim}")
            def tablo_ciz(baslik, tur_tipi):
                subset = data[data['tur'] == tur_tipi].copy()
                if not subset.empty:
                    st.subheader(baslik)
                    subset['Toplam Değer'] = subset['Toplam Değer'].apply(lambda x: f"{x:,.2f} {birim}")
                    st.dataframe(subset[['Varlık İsmi', 'Kod', 'Adet', 'Toplam Değer']], use_container_width=True, hide_index=True)
            tablo_ciz("💍 Madenler", "maden"); tablo_ciz("🇹🇷 BIST", "bist"); tablo_ciz("🇺🇸 ABD", "abd"); tablo_ciz("📦 Fonlar", "fon"); tablo_ciz("🪙 Kripto", "kripto"); tablo_ciz("💵 Döviz", "doviz"); tablo_ciz("📎 Diğer", "diger")

    elif sayfa == "Portföy Analizi":
        st.header("📊 Analiz")
        data = verileri_getir()
        if not data.empty and data['Toplam Değer'].sum() > 0:
            fig, ax = plt.subplots()
            ax.pie(data[data['Toplam Değer']>0]['Toplam Değer'], labels=data[data['Toplam Değer']>0]['Kod'], autopct='%1.1f%%', textprops={'color':'white'})
            fig.patch.set_alpha(0); st.pyplot(fig)

    elif sayfa == "Varlık Yönetimi":
        st.header("Varlık Yönetimi")
        with st.form("yeni_varlik_formu", clear_on_submit=True):
            t_es = {"Değerli Maden": "maden", "Borsa İstanbul": "bist", "ABD Borsaları": "abd", "Fon": "fon", "Kripto": "kripto", "Döviz": "doviz", "Diğer": "diger"}
            c1, c2, c3 = st.columns(3)
            y_k, s_t, y_v = c1.text_input("Varlık Kodu"), c2.selectbox("Tür", list(t_es.keys())), c3.number_input("Adet / Değer", min_value=0.0, format="%.4f")
            if st.form_submit_button("Kaydet"):
                df_m = pd.read_csv(PORTFOY_DOSYASI, sep=';')
                y_a, y_f = (1.0, y_v) if t_es[s_t] == 'diger' else (y_v, 0.0)
                pd.concat([df_m, pd.DataFrame([[y_k.upper(), y_a, t_es[s_t], y_f]], columns=['hisse_kodu','adet','tur','birim_fiyat'])], ignore_index=True).to_csv(PORTFOY_DOSYASI, sep=';', index=False)
                st.rerun()
        st.markdown('<p class="bilgi-notu">💡 Örnek: BTC, ALTIN, THYAO</p><p class="uyari-notu">⚠️ Hisse, fon, kripto para eklerken varlığın adetini; "Diğer" varlıkları eklerken ise varlığın değerini giriniz.</p>', unsafe_allow_html=True)
        
        df_m = pd.read_csv(PORTFOY_DOSYASI, sep=';').dropna(subset=['hisse_kodu'])
        if not df_m.empty:
            st.divider()
            for i, r in df_m.iterrows():
                with st.container():
                    col1, col2, col3, col4 = st.columns([2, 2, 1, 1])
                    col1.write(f"**{r['hisse_kodu']}**")
                    y_an = col2.number_input("Miktar", value=float(r['adet'] if r['tur'] != 'diger' else r['birim_fiyat']), key=f"ed_{i}")
                    if col3.button("🔄", key=f"up_{i}"):
                        if r['tur'] == 'diger': df_m.at[i, 'birim_fiyat'] = y_an
                        else: df_m.at[i, 'adet'] = y_an
                        df_m.to_csv(PORTFOY_DOSYASI, sep=';', index=False); st.rerun()
                    if col4.button("🗑️", key=f"dl_{i}"):
                        df_m.drop(i).to_csv(PORTFOY_DOSYASI, sep=';', index=False); st.rerun()
