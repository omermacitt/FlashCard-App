from sentence_transformers import SentenceTransformer, util

# Modeli yükle (bir kere indirir, sonra local kullanır)
model = SentenceTransformer("distiluse-base-multilingual-cased-v2")

# Örnek kelimeler
kelime1 = "yellow"
kelime2 = "yellow"

# Embed'leri hesapla
embedding1 = model.encode(kelime1, convert_to_tensor=True)
embedding2 = model.encode(kelime2, convert_to_tensor=True)

# Cosine similarity hesapla
similarity = util.cos_sim(embedding1, embedding2)

print("Benzerlik skoru:", similarity.item())
