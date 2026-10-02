# ragsec-lab

Self-hosted GraphRAG hattı (FastAPI + LangChain + Neo4j + Ollama) üzerinde güvenlik deneyleri için küçük laboratuvar.
Tüm veriler sahte. Sadece kendi altyapında çalıştır.

## Kurulum (Hafta 1, 1. gün)
1. `cp .env.example .env` ve `.env` içindeki şifre ile Ollama adresini doldur.
2. Modelin indirili olduğundan emin ol: `ollama pull llama3.2:3b`
3. `docker compose up -d --build` (Neo4j Aura kullanıyorsan yerel Neo4j çalışmaz, gerek de yok)
4. Veriyi yükle: `curl -X POST localhost:8000/seed`
5. Dene: `curl -X POST localhost:8000/ask -H 'content-type: application/json' -d '{"question":"Hangi container 8000 portunu açıyor?"}'`
6. Cevapta `generated_cypher` alanına bak: LLM'in ürettiği sorgu burada.

## Deney planı
- Hafta 1-2: OWASP LLM01/05/08'i oku, bu lab'da nerede ortaya çıkacağını yaz.
- Hafta 3-4: Her zafiyet için deney (notes/arastirma-gunlugu.md şablonuyla).
- Hafta 5-6: Bulguları raporla, her biri için önlem öner.

## Notlar
- Neo4j için Aura (bulut) ya da yerel container kullanılabilir. Yerel için: `docker compose --profile local up -d`.
- `/seed` komutu veritabanındaki HER ŞEYİ siler. Sadece bu laboratuvar için ayrılmış bir Aura örneğinde çalıştır.
- Bu kod henüz gerçek ortamda test edilmedi. İlk çalıştırmada hata çıkarsa çıktıyı paylaş, birlikte düzeltiriz.
