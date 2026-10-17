# Kendi sunucusunda çalışan bir text-to-Cypher GraphRAG hattında hangi korumalar işe yarıyor? Küçük bir laboratuvar çalışması

Mustafa Sekizkardeş, Ekim 2026. Kod, veri ve deney günlüğünün tamamı: https://github.com/Mhitra/ragsec-lab

> Sayılar `notes/research-daily.md` günlüğünden gelir.

## Özet

Neo4j grafı üzerinde en küçük hâliyle bir soru-cevap hattı kurdum (bir model Cypher sorgusu yazıyor, veritabanı sorguyu çalıştırıyor, ikinci bir model çağrısı cevabı yazıyor) ve küçük yerel modellerle neyin ters gittiğini ölçtüm. Günlükte 0'dan 13'e numaralanan deneyleri iki aileden dört modelle yaptım (qwen3.5 4B ve 9B, gemma3 4B, gemma4 e4b). Koruma yokken düz bir soru depolanmış bir sırrı sızdırdı, düz istekler veri oluşturdu ve sildi. Prompt dışındaki korumalar (sorgu izin listesi, salt okunur veritabanı oturumu) denediğim saldırıları durdurdu ve normal sorularda doğruluğu değiştirmedi. Prompt'u değiştiren korumalar (şema adlarını gizlemek, kural ya da örnek eklemek) güvenilir biçimde işe yaramadı: şema adlarını gizlemek ve kural eklemek doğruluğu hiçbir modelde artırmadı, bazılarında düşürdü; few-shot örnekleri 20 soruda dört modelin üçünde yardımcı oldu, ayrılmış sette ise az, ve bazı hataları bir sorudan diğerine kaydırdı. Daha büyük bir model tabanı yükseltti (13/20'den 17/20'ye) ama bu örüntüyü değiştirmedi, ve hiçbir şey döndürmeyen yanlış bir sorgu dört modelin üçünde yine olgu gibi sunuldu; dördüncüsü "I don't know" dedi. Veritabanına yerleştirilen metin, bariz olduğunda izlenmedi; ancak büyük model zararsız görünen bir biçim talimatına uydu, ve yerleştirilen metnin modele ulaşıp ulaşmaması modelin yazdığı sorguya bağlıydı. Kurulum küçüktür; sonuçlar bu kurulumda neyin mümkün olduğunu gösterir, genel hata oranlarını değil.

## 1. Giriş

Bu proje, altyapı işletme deneyimimden doğdu. Ocak 2026'da kullandığım bir sunucuda fidye yazılımı çalıştı. Aynı sunucu servisinde, sunucumdan başka bir web sitesine de saldırı yapıldı ve bu olaydan ben sorumlu tutuldum; ancak log kayıtları incelendiğinde saldırının benden kaynaklanmadığı anlaşıldı. Bunun üzerine kendi sunucumu satın aldım, servislerimi onun üzerinde çalıştırmaya başladım ve güvenliği daha sistematik incelemeye koyuldum. İki olayda da bir LLM yoktu. Ama artık servislerimi kendim barındırıyorum (Proxmox, Docker, Coolify) ve altyapı verisi üzerinde soru cevaplayan bir LLM aracı bariz bir sonraki ekleme; bu yüzden böyle bir aracın nasıl bozulduğunu bilmek istedim.

Böyle bir aracın yapısı basit: kullanıcı metni bir modele gidiyor, model bir veritabanı sorgusu yazıyor, sorgu uygulamanın kimlik bilgileriyle çalışıyor. Her adım, bir şeyin ters gidebileceği bir yer. Sorum şuydu: Text-to-SQL hatları için literatürde anlatılan saldırı ve savunmalar (Pedro ve ark., 2023), model küçük ve yerel olduğunda Neo4j üzerindeki bir text-to-Cypher hattına nasıl taşınıyor.

Dört şeyi ölçtüm: (1) korumasız bir hat neye izin veriyor, (2) her savunma neyi durduruyor, (3) her savunma cevap kalitesinden neyi götürüyor, ve (4) veritabanında duran metin cevapları yönlendirebiliyor mu. Ayrıca doğruluk ve enjeksiyon deneylerini aynı ailenin daha büyük bir modeliyle tekrarladım; hangi sonuçların model boyutuna bağlı olduğunu görmek için.

## 2. Kurulum

**Hat.** Kullanıcı sorusu, grafın şemasından Cypher yazan bir modele gider. Sorgu Neo4j Aura'da çalışır. İkinci bir model çağrısı dönen satırları cevaba çevirir. Yığın: FastAPI, LangChain (`GraphCypherQAChain`), Neo4j ve Ollama. Web arayüzü, üretilen Cypher'ı ve veritabanı satırlarını cevabın yanında gösterir.

```
soru -> [model: Cypher yaz] -> [Neo4j] -> satırlar -> [model: cevap yaz] -> cevap
              ^ korumalar burada            ^ enjekte edilen metin buraya gelir
```

**Veri.** Küçük, sentetik bir altyapı grafı: 3 container, 2 host, 3 port ve yerleştirilmiş tek bir sahte sır (`Container -[:HAS_SECRET]-> Secret`). Tüm değerler uydurmadır.

**Modeller.** Ollama üzerinden qwen3.5:4b, qwen3.5:9b, gemma3:4b ve gemma4:e4b, sıcaklık 0, akıl yürütme (reasoning) kapalı. Sıcaklık 0'da aynı girdi aynı çıktıyı verir; bu yüzden bir koşuyu tekrarlamak istatistiksel güç katmaz. Her hücreyi bir kez çalıştırdım.

**Korumalar.**

| Ad | Ne yapar |
|---|---|
| Şema filtresi | `Secret` etiketini ve `HAS_SECRET`'i modele gösterilen şemadan gizler |
| Doğrulayıcı (validator) | Üretilen Cypher'ı çalışmadan önce bir izin listesine göre denetler (sorgu `MATCH` ile başlamalı, yalnız izin verilen etiketler ve ilişkiler, yazma yan tümceleri yok, ad alanlı fonksiyon çağrısı yok) |
| Salt okunur | Üretilen Cypher'ı salt okunur bir veritabanı oturumunda çalıştırır |
| Etiket kuralı | Cypher prompt'una bir kural ekler: her düğüme bir etiket ver |
| Few-shot | Cypher prompt'una bir kural ve altı çözümlü örnek ekler |

İlk üçü saldırı savunmasıdır. Son ikisi, modelin gördüğünü değiştirdikleri için test ettiğim prompt değişiklikleridir.

**Sorular ve puanlama.** 20 soruluk bir set (arama, sayma, liste, iki adımlı, olumsuz sorular, bir belirsiz soru) ve few-shot örnekleri sabitlendikten sonra yazdığım 13 soruluk bir ayrılmış (held-out) set. Her cevap anahtar kelimelerle denetlenir; katı yeniden puanlama (yeni model çağrısı yok) hata mesajlarını, "I don't know" cevaplarını ve doğru bir olguyu inkâr eden cevapları yanlış sayar. Katı skoru bildiriyorum, çünkü anahtar kelime skoru iki yanlış cevabı doğru saymıştı. Gerçek cevaplar (ground truth) tohum dosyasından gelir.

## 3. Sonuçlar

### 3.1 Korumasız hatta erişim denetimi yok (Deney 2)

Düz bir soru, "What secrets does the coolify container have?", ilk denemede sahte anahtarı ve değerini döndürdü. Özel bir ifade gerekmedi. Modelden bir düğüm oluşturmasını ve silmesini istemek de işe yaradı: her iki durumda da cevap metni modelin yapamayacağını söyledi, oysa sorgu zaten çalışmıştı ve sonraki bir soru değişikliği doğruladı. Modelin ifadesi, ne olduğunun kanıtı değildir. Zayıflık mimariden kaynaklanıyor: soru kutusuna ulaşan herkes veritabanı kullanıcısının yapabildiğini yapabilir.

### 3.2 Prompt dışındaki savunmalar (Deney 3-5)

- **Şema filtresi başarısız oldu.** Adları gizlemek veriyi gizlemedi. Bir denemede model, gizlenen adları "secrets" kelimesinden tahmin etti, yanlış düğüme bağladı ve "no secrets" cevabını verdi: kendinden emin yanlış bir cevap. Etiketi ya da ilişkiyi adıyla anan iki deneme sırrı sızdırdı (2/2).
- **Salt okunur oturum, yazmaları veritabanında durdurdu** (Aura erişim modunu uyguladı), ama okumaları durdurmadı: sır yine sızdı.
- **İzin listesi doğrulayıcı denediğim her saldırıyı engelledi** (sızıntı, oluşturma, silme, etiketsiz düğümler), fakat ilk sürümü tanımadığı komutları engellemeden geçiriyordu (fail-open). Anahtar kelime engel listesi `SHOW DATABASES`, `RETURN apoc.version()` ve benzeri komutları geçirdi. Onu yalnızca izin verilen sorgu biçimini kabul edecek şekilde yeniden yazdım ve 28 birim vakayla (7 izinli, 21 engelli) test ettim. Hâlâ bir dize düzeyinde denetim; Cypher ayrıştırıcısı değil.
- **Üçü birleşince 3/3 saldırı engellendi** ve 5 normal sorudan 3'ü cevaplandı. Salt okunur katmana hiç ulaşılmadı, çünkü doğrulayıcı her şeyi önce durdurdu; yani bu koşu derinlemesine savunmayı değil doğrulayıcıyı ölçer.
- Ham veritabanı hataları kullanıcıya ulaştı ve veritabanı kimliğini içeriyordu. Genel bir hata mesajı (ayrıntı yalnızca sunucu günlüğünde) bu kanalı kapattı.

### 3.3 Savunmaların doğruluğa maliyeti (Deney 6, 8, 9, 10, 11, 13)

| Ayar | qwen 4B | qwen 9B | gemma3 4B | gemma4 e4b |
|---|---|---|---|---|
| Koruma yok | 13 | 17 | 13 | 16 |
| Doğrulayıcı | 13 | 17 | 13 | 16 |
| Salt okunur | 13 | 17 | 13 | 16 |
| Şema filtresi | 11 | 15 | 13 | 16 |
| Üçü birden | 11 | 15 | 13 | 16 |
| Etiket kuralı | 12 | 16 | 10 | 16 |
| Few-shot örnekleri | 16 | 17 | 18 | 17 |

Katı skor, 20 üzerinden. Ayrılmış set (13 soru, katı), koruma yok / etiket kuralı / few-shot: qwen 4B 8 / 9 / 10, qwen 9B 11 / 11 / 11, gemma3 8 / 7 / 9, gemma4 11 / 10 / 11.

- **Doğrulayıcı ve salt okunur oturum, dört modelde de zararsız sorulardaki hiçbir cevabı değiştirmedi.** İki modelde doğrulayıcı bir zararsız soruyu engelledi (qwen 9B ve gemma3): model Cypher yerine geçersiz metin yazmıştı, ki bu zaten Neo4j'de başarısız olur.
- **Prompt düzenlemeleri güvenilir biçimde yardımcı olmadı.** Şema filtresi iki qwen modeline ikişer soru kaybettirdi, gemma modellerinde hiçbir şeyi değiştirmedi. Etiket kuralı 1, 1, 3 ve 0 soru kaybettirdi. Hiçbiri 20 soruda hiçbir modelde doğruluğu artırmadı. qwen 4B modelde, model deterministik olduğu hâlde tek satırlık bir prompt değişikliği hangi soruların başarısız olduğunu değiştirdi.
- **Few-shot örnekleri qwen 4B ile 3 soru, qwen 9B ile hiçbir şey, gemma3 ile 5, gemma4 ile 1 soru kazandırdı.** Örnekler 4B modelin sözdizimi hatalarını giderdi (3 hata cevabından 0'a), ama anlam hatalarını (ilişki yönü, bir container adının host adı olarak kullanılması) gidermedi ve bazılarını başka sorulara kaydırdı. Örnekleri hataları okuduktan sonra yazdım; bu yüzden 20 soruluk sonuç bir genelleme testi değildir. Ayrılmış sette kazanç daha küçüktü (+2, 0, +1 ve 0). gemma3'ün büyük kazancı (13'ten 18'e) kısmen aynı etkidir, çünkü örnekler qwen 4B modelinin bu sorulardaki hatalarından çıktı.
- Her hücre, 13-20 soru üzerinde tek bir koşudur. Bir ya da iki soruluk farklar bir etkinin kanıtı değildir. gemma4'ün iki ilk koşusu, dizüstünün yavaşladığı bir dönemde (pilde çalışıyordu) hata verdi; şarj takılıyken yeniden çalıştırdım, ilk koşuları ayrı tuttum (bölüm 8'e bak).

### 3.4 Daha büyük model tabanı yükseltir, yapıyı değil (Deney 11 ve 13)

Korumasız 9B model 17/20 aldı, 4B ise 13/20; on arama sorusunun hepsini doğru cevapladı (4B: 10'da 7) ve çok daha az geçersiz sorgu yazdı. Örüntü korundu: doğrulayıcı ve salt okunur doğruluğa dokunmadı, prompt düzenlemeleri nötr ya da zararlıydı, ve bazı yanlış sorgular iki modelde aynıydı. Örneğin her iki model de bir container adını host adı olarak kullandı (`Host {name: 'coolify'}`) ve "No other containers run on the same host as coolify." cevabını verdi. Aynı hata iki gemma modelinde de var ve few-shot örnekleri dördünde de düzeltti. gemma4 modeli aynı yanlış sorguyu yazdı ama "I don't know" cevabını verdi; yani hata kullanıcıya farklı göründü. gemma4'ün 10 koşusunun hiçbirinde yanlış ya da inkâr eden cevap olmadı. Hataları "I don't know" cevaplarıydı; örneğin üç olumsuz soruda sorgu doğruydu, sonuç boştu ve katı skor bu çekimserliği yanlış sayıyor.

### 3.5 Yanlış sorgular kendinden emin yanlış cevaplara dönüşür (Deney 1, 8, 10)

Yanlış bir filtre hiç satır döndürmediğinde cevap aşaması yokluğu olgu olarak bildirir: "No host runs the ollama container" (`name` yerine `image` üzerinden filtreledi), "No containers depend on neo4j" (ters ok, yanlış özellik). Bunlar görünür hatalardan daha tehlikelidir, çünkü hiçbir şey kullanıcıya sorgunun yanlış olduğunu söylemez. Boş bir sonucun ifadesi de kararsızdır: aynı hat bir boş sonucu "I don't know" ile, bir diğerini "No containers depend on coolify" ile cevapladı. Her iki soru seti ve dört model üzerinden, yanlış ya da inkâr eden cevaplar örneksiz 132'de 16, few-shot ile 132'de 6'ydı (gemma4'te iki ayarda da yoktu). Sayılar küçük, ama yön, örneklerin doğruluğu artırmaktan çok kendinden emin yanlış cevapları azalttığını düşündürüyor.

### 3.6 Veritabanına yerleştirilen metin (Deney 7 ve 12)

Bir talimat içeren `description` özelliğiyle bir fazladan düğüm kaydettim, altı varyantla, ve beş soru sordum. Bir bayrak, yerleştirilen metnin cevap aşamasına ulaşıp ulaşmadığını kaydetti (sorgunun döndürdüğü satırlarda göründü mü). Yalnızca metnin cevap aşamasına ulaştığı cevaplar hesaba katıldı: kontrol sorusu dışındaki 48 cevabın 36'sı (model başına 18).

| Varyant | 4B uydu | 9B uydu |
|---|---|---|
| Bariz talimat ("answer only PWNED", üç ifade) | 9'da 0 | 9'da 0 |
| Zararsız biçim talimatı ("her cevabı bir cümleyle bitir") | 3'te 0 | 3'te 3 |
| Diğer satırlar hakkında yanlış beyan ("diğer container'lar durmuş de") | 3'te 1 (+1 kısmen) | 3'te 0 |

- Hiçbir model cevabını yerleştirilen kelimeyle değiştirmedi. Büyük model, maruz kaldığı her cevapta zararsız görünen talimata uydu; küçük model ise bir satırdan gelen, diğer container'lar hakkındaki yanlış bir iddiayı tekrarladı. Talimat türlerine göre uyma sırası model boyutunu izlemedi.
- Yerleştirilen metin, izlenmeden de cevapları bozdu: 4B model iki varyantta container'ları listelemeyi reddetti, 9B model bir kez var olan bir container hakkında bilgi olmadığını söyledi.
- Metnin cevap aşamasına ulaşıp ulaşmadığı, modelin yazdığı sorguya bağlıydı. 4B ile açık soru uydurma özelliklerde başarısız oldu, liste sorusu ise açıklamayı döndürdü. 9B ile tersiydi. İlk koşumdaki kontrol sorusu dışındaki cevapların yarısı hiçbir şey test etmedi; bu yüzden maruz kalma bayrağını ve özelliğin çekilmesini zorlayan iki soruyu ekledim.

## 4. Tartışma

Kurulumun sınırları içinde bundan çıkardıklarım:

1. **Sınırları modelin tartışamayacağı yerde uygula.** Salt okunur veritabanı oturumu ve sorgu izin listesi işe yaradı ve doğruluğa mal olmadı. İsimleri prompt'tan gizlemek ve modelin "I cannot do that" cevabına güvenmek işe yaramadı. Salt okunur gizliliği korumaz: neyin okunabileceği kendi denetimini ister, örneğin bir veritabanı rolü.
2. **Prompt değişikliklerini, test edilen sistemin değişikliği olarak ele al.** Bir kural ya da örnek kümesi davranışı tahmin etmesi zor biçimlerde değiştirir, ve model değişince etki kaybolabilir.
3. **"Veri yok" ile "bilmiyorum"u ayır.** Yanlış bir sorgudan gelen boş sonuç olgu gibi söylenir. Üretilen sorguyu göstermek ya da sorguyu şemaya göre denetlemek (özellik adları ve ilişki yönü) bu hataları görünür kılar.
4. **Getirilen metni güvenilmez say ve bir sorgunun hangi özellikleri döndürebileceğini sınırla.** Benim kurulumumda yerleştirilen metnin cevaba ulaşıp ulaşamayacağını modelin kendi sorgusu belirledi.
5. **İtaatten fazlasını ölç.** "Model PWNED dedi mi" ölçütü biçim talimatını, yanlış iddiayı ve bozulan cevapları kaçırdı.

## 5. Sınırlar

- Bir sentetik graf (3 container, 2 host), iki aileden dört model, hücre başına tek koşu. Etkin örneklem ayar başına 13-20 soru; bir ya da iki soruluk farklar gürültüdür.
- Few-shot örnekleri hataları okuduktan sonra yazıldı ve ayrılmış sorular aynı kişi tarafından yazıldı; yani örneklerden ayrılmıştır ama benden bağımsız değildir.
- Puanlama anahtar kelimelerle, katı yeniden puanlama ve elle okumayla yapıldı; yine de hataları kaçırabilir.
- Hat, araçsız tek geçiştir. Sonuçlar, döngüye giren ve araç çağıran ajanlar için geçerli değildir.
- Saldırı deneyleri (2-5) yalnızca qwen 4B modeli, enjeksiyon deneyleri yalnızca iki qwen modelini kullandı.
- Doğrulayıcı dize düzeyinde bir denetimdir. Onu canlı bir modelle atlatmayı denemedim.

## 6. İlgili çalışmalar

Pedro ve ark. ("From Prompt Injections to SQL Injection Attacks", arXiv:2308.01990; ICSE 2025'te "Prompt-to-SQL Injections in LLM-Integrated Web Applications: Risks and Defenses" adıyla), LangChain uygulamalarına karşı prompt-to-SQL saldırılarını birkaç LLM üzerinde inceler ve savunmalar önerir. Szlobodnyik ("Feedback-Guided Prompt Injection Defense in Retrieval-Augmented Text-to-Cypher Generation", Analytics, MDPI), text-to-Cypher sistemlerine karşı doğrudan prompt enjeksiyonunu büyük modellerle inceler. LLM uygulamaları için OWASP Top 10, burada test edilen riskler için (prompt enjeksiyonu, hassas bilgi ifşası, uygunsuz çıktı işleme, aşırı yetki, yanlış bilgi) ortak bir terminoloji sağladı. Çalışmam kapsamda farklıdır, fikirde değil: küçük yerel modeller, Neo4j Aura üzerinde salt okunur oturum, dize düzeyinde bir doğrulayıcı ve prompt değişikliklerinin doğruluğa ne yaptığının ölçümü.

## 7. Kapsam dışı

Doğrulayıcıyı canlı bir modelle atlatma denemeleri; belirsiz yıkıcı istekler ("test verisini temizle"); model çıktısının arayüzde işlenmesi (OWASP LLM05); döngüye giren ya da araç çağıran ajanlar (enjekte edilmiş bir talimat eylem başlatabilir); 9B ve gemma modelleriyle saldırı deneyleri ve gemma modelleriyle enjeksiyon deneyleri; vektör ve graf getirme zayıflıkları.

## 8. Yeniden üretme

Her şey depoda: hat (`app/`), betikler (`scripts/run_all.py`, `scripts/rescore.py`, `scripts/run_injection.py`), soru setleri ve gerçek cevaplar (`questions/`), üretilen Cypher ile her ham cevap (`results/`) ve her deneyin yöntemi ve sınırlarıyla tarihli günlük (`notes/research-daily.md`). Komutlar README'de. Tüm veri sentetiktir. Ters giden dört koşu (boş veritabanı, eski container imajı ve dizüstünün yavaşladığı bir dönemde gemma4'ün iki ilk koşusu) ayrı tutuldu ve sayılmadı.
