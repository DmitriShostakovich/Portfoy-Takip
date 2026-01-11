import streamlit as st
import pandas as pd
import yfinance as yf
from tefas import Crawler
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
    st.markdown("<h1 style='text-align: center;'>🔐 Kişisel Portföy Yönetimi</h1>", unsafe_allow_html=True)
    tab1, tab2 = st.tabs(["Giriş Yap", "Yeni Profil Oluştur"])
    
    with tab1:
        with st.form("giris_formu"):
            k_adi = st.text_input("Kullanıcı Adı").strip()
            sifre = st.text_input("Şifre", type="password").strip()
            if st.form_submit_button("Giriş Yap", use_container_width=True):
                df_k = pd.read_csv('kullanicilar.csv', sep=';', dtype=str).fillna("")
                user = df_k[(df_k['kullanici_adi'] == k_adi) & (df_k['sifre'] == sifre)]
                if not user.empty:
                    st.session_state["giris_yapildi"] = True
                    st.session_state["aktif_kullanici"] = k_adi
                    st.rerun()
                else: 
                    st.error("Kullanıcı adı veya şifre hatalı!")

    with tab2:
        with st.form("profil_formu"):
            y_kadi = st.text_input("Yeni Kullanıcı Adı").strip()
            y_sifre = st.text_input("Yeni Şifre", type="password").strip()
            if st.form_submit_button("Profil Oluştur"):
                df_k = pd.read_csv('kullanicilar.csv', sep=';', dtype=str).fillna("")
                if y_kadi and y_sifre:
                    if y_kadi in df_k['kullanici_adi'].values:
                        st.warning("Bu kullanıcı adı zaten mevcut!")
                    else:
                        yeni = pd.DataFrame([[y_kadi, y_sifre]], columns=['kullanici_adi', 'sifre'])
                        pd.concat([df_k, yeni], ignore_index=True).to_csv('kullanicilar.csv', sep=';', index=False)
                        st.success("Profil başarıyla oluşturuldu!")
                else:
                    st.error("Alanları boş bırakmayın!")

# --- 3. ANA UYGULAMA ---
if not st.session_state["giris_yapildi"]:
    giris_sistemi()
else:
    PORTFOY_DOSYASI = f"portfoy_{st.session_state['aktif_kullanici']}.csv"
    GECMIS_DOSYASI = f"gecmis_{st.session_state['aktif_kullanici']}.csv"
    
    if not os.path.exists(GECMIS_DOSYASI):
        pd.DataFrame(columns=['tarih', 'toplam_tl', 'toplam_usd']).to_csv(GECMIS_DOSYASI, sep=';', index=False)

    st.markdown("""<style>.stApp { background-color: #0e1117; color: white; } .bilgi-notu { color: #888; font-size: 0.9rem; margin-top: 5px; } .uyari-notu { color: #ffcc00; font-size: 0.85rem; margin-top: 5px; }</style>""", unsafe_allow_html=True)

    def verileri_getir():
        if not os.path.exists(PORTFOY_DOSYASI):
            pd.DataFrame(columns=['hisse_kodu', 'adet', 'tur', 'birim_fiyat']).to_csv(PORTFOY_DOSYASI, sep=';', index=False)
            return pd.DataFrame(), 1.0
        
        df = pd.read_csv(PORTFOY_DOSYASI, sep=';').dropna(subset=['hisse_kodu'])
        if df.empty: return df, 1.0
        df.columns = df.columns.str.strip().str.lower()
        
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
                if tur == 'diger': 
                    f, n = float(row['birim_fiyat']), kod
                elif tur == 'fon':
                    fv = tefas.fetch(start=bas_tar, end=bit_tar, name=kod)
                    if not fv.empty: 
                        f, n = fv['price'].iloc[-1], fv['title'].iloc[-1]
                    else: 
                        f, n = 0, kod
                else:
                    ykod = kod
                    if kod in ["BTC", "ETH", "SOL"]: 
                        ykod, n = f"{kod}-USD", {"BTC":"Bitcoin","ETH":"Ethereum","SOL":"Solana"}[kod]
                    elif kod == "ALTIN": ykod, n = "GC=F", "Gram Altın"
                    elif kod == "GUMUS": ykod, n = "SI=F", "Gram Gümüş"
                    else:
                        if tur == 'bist' and not kod.endswith(".IS"): ykod = f"{kod}.IS"
                        ykod = {"USD": "USDTRY=X", "EUR": "EURTRY=X"}.get(kod, ykod)
                        tick = yf.Ticker(ykod)
                        n = tick.info.get('shortName', kod)
                    
                    hist = yf.Ticker(ykod).history(period="5d")
                    f = hist['Close'].iloc[-1] if not hist.empty else 0
                    
                    if tur in ['abd', 'kripto']: f *= usd_kur
                    if kod in ["ALTIN", "GUMUS"]: f = (f / 31.1035) * usd_kur
                
                fiyatlar.append(f); isimler.append(n)
            except: 
                fiyatlar.append(0); isimler.append(kod)
            
        df['Varlık İsmi'], df['birim_fiyat'] = isimler, fiyatlar
        df['Toplam Değer'] = df.apply(lambda r: r['birim_fiyat'] if r['tur'] == 'diger' else r['adet'] * r['birim_fiyat'], axis=1)
        
        # --- GELİŞİM GRAFİĞİ DÜZELTME VE KAYIT ---
        toplam_tl = round(df['Toplam Değer'].sum(), 2)
        bugun = datetime.now().strftime("%Y-%m-%d")
        
        if toplam_tl > 0:
            gecmis_df = pd.read_csv(GECMIS_DOSYASI, sep=';').dropna()
            if bugun not in gecmis_df['tarih'].values:
                yeni_kayit = pd.DataFrame([[bugun, toplam_tl, round(toplam_tl/usd_kur, 2)]], columns=['tarih','toplam_tl','toplam_usd'])
                pd.concat([gecmis_df, yeni_kayit], ignore_index=True).to_csv(GECMIS_DOSYASI, sep=';', index=False)
            else:
                idx = gecmis_df[gecmis_df['tarih'] == bugun].index[0]
                gecmis_df.at[idx, 'toplam_tl'] = toplam_tl
                gecmis_df.at[idx, 'toplam_usd'] = round(toplam_tl / usd_kur, 2)
                gecmis_df.to_csv(GECMIS_DOSYASI, sep=';', index=False)

        if st.session_state["para_birimi"] == "USD":
            df['Toplam Değer'] /= usd_kur
            df['birim_fiyat'] /= usd_kur
        return df.rename(columns={'hisse_kodu': 'Kod', 'adet': 'Adet'}), usd_kur

    # --- SIDEBAR ---
    with st.sidebar:
        st.title(f"👤 {st.session_state['aktif_kullanici']}")
        st.divider()
        sayfa = st.radio("Menü", ["Portföyü İzle", "Gelişim Grafiği", "Portföy Analizi", "Varlık Yönetimi"])
        st.divider()
        if st.button("🚪 Çıkış Yap", use_container_width=True):
            st.session_state["giris_yapildi"] = False
            st.rerun()

    # --- SAYFALAR ---
    if sayfa == "Portföyü İzle":
        c1, c2 = st.columns([3, 1])
        c1.header("Anlık Portföy Durumu")
        if c2.button("Döviz Değiştir"):
            st.session_state["para_birimi"] = "USD" if st.session_state["para_birimi"] == "TL" else "TL"
            st.rerun()
        
        data, _ = verileri_getir()
        if not data.empty:
            birim = "$" if st.session_state["para_birimi"] == "USD" else "TL"
            st.metric("Toplam Portföy Değeri", f"{data['Toplam Değer'].sum():,.2f} {birim}")
            for t in ["maden", "bist", "abd", "fon", "kripto", "doviz", "diger"]:
                subset = data[data['tur'] == t].copy()
                if not subset.empty:
                    st.subheader(t.upper())
                    subset['Toplam Değer'] = subset['Toplam Değer'].apply(lambda x: f"{x:,.2f} {birim}")
                    st.dataframe(subset[['Varlık İsmi', 'Kod', 'Adet', 'Toplam Değer']], use_container_width=True, hide_index=True)

    elif sayfa == "Gelişim Grafiği":
        st.header("📈 Zaman İçindeki Değişim")
        gecmis_df = pd.read_csv(GECMIS_DOSYASI, sep=';')
        if not gecmis_df.empty:
            sutun = 'toplam_tl' if st.session_state["para_birimi"] == "TL" else 'toplam_usd'
            st.line_chart(gecmis_df.set_index('tarih')[sutun])
            st.info("Grafik günlük kapanış değerlerinizi takip eder.")
        else:
            st.warning("Veri birikmesi bekleniyor...")

    elif sayfa == "Portföy Analizi":
        st.header("📊 Varlık Dağılımı")
        data, _ = verileri_getir()
        if not data.empty:
            fig, ax = plt.subplots()
            ax.pie(data[data['Toplam Değer']>0]['Toplam Değer'], labels=data[data['Toplam Değer']>0]['Kod'], autopct='%1.1f%%', textprops={'color':'white'})
            fig.patch.set_alpha(0); st.pyplot(fig)

    elif sayfa == "Varlık Yönetimi":
        st.header("Varlık Yönetimi")
        with st.form("yeni_v", clear_on_submit=True):
            t_es = {"Maden": "maden", "BIST": "bist", "ABD": "abd", "Fon": "fon", "Kripto": "kripto", "Döviz": "doviz", "Diğer": "diger"}
            c1, c2, c3 = st.columns(3)
            y_k, s_t, y_v = c1.text_input("Varlık Kodu (Örn: THYAO)").upper().strip(), c2.selectbox("Varlık Türü", list(t_es.keys())), c3.number_input("Adet / Toplam Değer", format="%.4f")
            if st.form_submit_button("Kaydet / Üzerine Ekle"):
                df_m = pd.read_csv(PORTFOY_DOSYASI, sep=';')
                # Otomatik Üzerine Ekleme
                if y_k in df_m['hisse_kodu'].values:
                    idx = df_m[df_m['hisse_kodu'] == y_k].index[0]
                    if t_es[s_t] == 'diger': df_m.at[idx, 'birim_fiyat'] += y_v
                    else: df_m.at[idx, 'adet'] += y_v
                    st.success(f"{y_k} miktarı güncellendi!")
                else:
                    yeni_v = pd.DataFrame([[y_k, 1.0 if t_es[s_t]=='diger' else y_v, t_es[s_t], y_v if t_es[s_t]=='diger' else 0.0]], columns=['hisse_kodu','adet','tur','birim_fiyat'])
                    df_m = pd.concat([df_m, yeni_v], ignore_index=True)
                    st.success(f"{y_k} portföye eklendi!")
                df_m.to_csv(PORTFOY_DOSYASI, sep=';', index=False); st.rerun()
        
        st.markdown('<p class="bilgi-notu">💡 Mevcut bir kodu girerseniz yeni miktar eskisinin üzerine eklenir.</p>', unsafe_allow_html=True)
        st.markdown('<p class="bilgi-notu">💡 Örnek: BTC, ALTIN, THYAO, IDH</p>', unsafe_allow_html=True)
        st.markdown('<p class="uyari-notu">⚠️ Hisse, fon, kripto için adet; "Diğer" için toplam TL değerini giriniz.</p>', unsafe_allow_html=True)
        
        df_m = pd.read_csv(PORTFOY_DOSYASI, sep=';').dropna(subset=['hisse_kodu'])
        if not df_m.empty:
            st.divider()
            for i, r in df_m.iterrows():
                c1, c2, c3, c4 = st.columns([2, 2, 1, 1])
                c1.write(f"**{r['hisse_kodu']}**")
                yeni_val = c2.number_input("Miktar/Değer", value=float(r['adet'] if r['tur'] != 'diger' else r['birim_fiyat']), key=f"edit_{i}")
                if c3.button("🔄", key=f"upd_{i}"):
                    if r['tur'] == 'diger': df_m.at[i, 'birim_fiyat'] = yeni_val
                    else: df_m.at[i, 'adet'] = yeni_val
                    df_m.to_csv(PORTFOY_DOSYASI, sep=';', index=False); st.rerun()
                if c4.button("🗑️", key=f"del_{i}"):
                    df_m.drop(i).to_csv(PORTFOY_DOSYASI, sep=';', index=False); st.rerun()
