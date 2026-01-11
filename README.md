Bu portföy takip uygulamasını kendim için ai yardımıyla yaklaşık 5-6 saatte yaptım. İlk proje denememdir. Burdan sonraki yazıları da tamamen gemini'ye yazdırdım.


Bu proje, bireysel yatırımcıların farklı platformlardaki (Borsa İstanbul, ABD Borsaları, Kripto Paralar, Yatırım Fonları ve Değerli Madenler) tüm varlıklarını tek bir merkezden, anlık fiyatlarla takip etmelerini sağlayan **Python tabanlı bir Portföy Yönetim Sistemidir**.

İşte bu projeyi öne çıkaran temel özellikler ve teknik altyapı:

### Projenin Temel Amacı

Yatırımcıların karmaşıklaşan varlık dağılımlarını görselleştirmek ve "Şu an toplamda ne kadar param var?" sorusuna saniyeler içinde, TL veya Dolar bazında yanıt vermektir.

### Öne Çıkan Teknik Özellikler

* **Çoklu Varlık Desteği:** Hisse senetlerinden kripto paralara, gram altından yatırım fonlarına kadar geniş bir yelpazede veri çekebilir.
* **Anlık Veri Entegrasyonu:** `yfinance` ve `tefas` kütüphanelerini kullanarak piyasa verilerini canlıya yakın bir şekilde günceller.
* **Gelişim Grafiği:** Kullanıcının portföy değerini her gün otomatik olarak kaydederek zaman içindeki büyüme veya küçülme trendini bir çizgi grafiği üzerinde sunar.
* **Varlık Analizi:** Portföyün hangi varlık sınıflarına (yüzde kaç nakit, yüzde kaç hisse vb.) dağıldığını pasta grafiği ile görselleştirir.
* **Kişiselleştirilmiş Kullanıcı Deneyimi:** Her kullanıcı için ayrı bir profil yapısı sunar; böylece herkes kendi şifresiyle sadece kendi portföyünü yönetir.

### Kullanılan Teknolojiler

* **Arayüz:** Modern ve interaktif bir web arayüzü için **Streamlit**.
* **Veri İşleme:** Verilerin analizi ve CSV formatında saklanması için **Pandas**.
* **Piyasa Verileri:** Global veriler için **Yahoo Finance (yfinance)** ve yerel fon verileri için **TEFAŞ Crawler**.
* **Görselleştirme:** Analitik grafikler için **Matplotlib**.

### Kullanıcı Dostu Detaylar

* **Otomatik Üzerine Ekleme:** Aynı varlıktan yeni alımlar yapıldığında eski miktarın üzerine otomatik toplama yapar.
* **Döviz Çevirici:** Tek bir butonla tüm portföyü TL'den USD'ye (veya tam tersi) çevirebilir.
* **Hatalı Veri Koruması:** Piyasa kapalıyken veya veri çekme hatası oluştuğunda hatalı (sıfır) değerlerin grafik geçmişini bozmasını engeller.

Bu proje, bir yatırımcının kendi bilgisayarında çalışan, verilerini dışarıya sızdırmayan ve tamamen ücretsiz araçlarla inşa edilmiş **profesyonel bir finansal asistan** niteliğindedir.
