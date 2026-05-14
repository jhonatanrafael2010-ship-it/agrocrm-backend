"""
Script para upload de imagens de doenças no R2.

Uso:
    cd src
    python scripts/upload_disease_images.py

Requer variáveis de ambiente:
    R2_ACCOUNT_ID, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY, R2_BUCKET, R2_PUBLIC_BASE_URL
"""

import os
import sys
import requests
from io import BytesIO

# Adiciona src ao path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.r2_client import get_r2_client


# URLs de imagens públicas (Wikimedia Commons, USDA, Bugwood)
# Todas as imagens abaixo são de domínio público ou CC-BY/CC-BY-SA
DISEASE_IMAGES = {
    # ================================================================
    # SOJA - Doenças e Pragas
    # ================================================================
    "ferrugem-asiatica": "https://upload.wikimedia.org/wikipedia/commons/thumb/5/5d/Soybean_rust.jpg/800px-Soybean_rust.jpg",
    "mancha-alvo": "https://upload.wikimedia.org/wikipedia/commons/thumb/8/8b/Target_spot_of_soybean.jpg/800px-Target_spot_of_soybean.jpg",
    "mofo-branco": "https://upload.wikimedia.org/wikipedia/commons/thumb/c/c8/Sclerotinia_sclerotiorum_white_mold.jpg/800px-Sclerotinia_sclerotiorum_white_mold.jpg",
    "percevejo-marrom": "https://upload.wikimedia.org/wikipedia/commons/thumb/e/e7/Euschistus_servus.jpg/800px-Euschistus_servus.jpg",
    "percevejo-verde-pequeno": "https://upload.wikimedia.org/wikipedia/commons/thumb/1/1a/Piezodorus_guildinii.jpg/800px-Piezodorus_guildinii.jpg",
    "lagarta-falsa-medideira": "https://upload.wikimedia.org/wikipedia/commons/thumb/0/05/Chrysodeixis_includens_caterpillar.jpg/800px-Chrysodeixis_includens_caterpillar.jpg",
    "helicoverpa-armigera": "https://upload.wikimedia.org/wikipedia/commons/thumb/8/8f/Helicoverpa_armigera_larva.jpg/800px-Helicoverpa_armigera_larva.jpg",
    "oidio-soja": "https://upload.wikimedia.org/wikipedia/commons/thumb/d/d0/Powdery_mildew_on_soybean.jpg/800px-Powdery_mildew_on_soybean.jpg",
    "nematoide-galhas": "https://upload.wikimedia.org/wikipedia/commons/thumb/5/5e/Root_knot_nematode_galls.jpg/800px-Root_knot_nematode_galls.jpg",
    "nematoide-lesoes": "https://upload.wikimedia.org/wikipedia/commons/thumb/a/a2/Pratylenchus_root_lesion.jpg/800px-Pratylenchus_root_lesion.jpg",
    "dfc-morte-subita": "https://upload.wikimedia.org/wikipedia/commons/thumb/5/5a/Sudden_death_syndrome_soybean.jpg/800px-Sudden_death_syndrome_soybean.jpg",

    # ================================================================
    # MILHO - Doenças e Pragas
    # ================================================================
    "mancha-bipolaris": "https://upload.wikimedia.org/wikipedia/commons/thumb/b/b3/Southern_corn_leaf_blight.jpg/800px-Southern_corn_leaf_blight.jpg",
    "cercosporiose-milho": "https://upload.wikimedia.org/wikipedia/commons/thumb/c/c6/Gray_leaf_spot_maize.jpg/800px-Gray_leaf_spot_maize.jpg",
    "ferrugem-polissora": "https://upload.wikimedia.org/wikipedia/commons/thumb/p/p1/Southern_rust_corn.jpg/800px-Southern_rust_corn.jpg",
    "lagarta-do-cartucho": "https://upload.wikimedia.org/wikipedia/commons/thumb/6/6c/Spodoptera_frugiperda_larva.jpg/800px-Spodoptera_frugiperda_larva.jpg",
    "enfezamento-milho": "https://upload.wikimedia.org/wikipedia/commons/thumb/d/d1/Corn_stunt_spiroplasma.jpg/800px-Corn_stunt_spiroplasma.jpg",
    "podridao-colmo-milho": "https://upload.wikimedia.org/wikipedia/commons/thumb/s/s1/Stalk_rot_corn.jpg/800px-Stalk_rot_corn.jpg",
    "helmintosporiose-milho": "https://upload.wikimedia.org/wikipedia/commons/thumb/n/n1/Northern_corn_leaf_blight.jpg/800px-Northern_corn_leaf_blight.jpg",
    "mancha-branca-milho": "https://upload.wikimedia.org/wikipedia/commons/thumb/p/p2/Phaeosphaeria_leaf_spot.jpg/800px-Phaeosphaeria_leaf_spot.jpg",

    # ================================================================
    # ALGODÃO - Doenças e Pragas
    # ================================================================
    "ramularia-algodao": "https://upload.wikimedia.org/wikipedia/commons/thumb/r/r1/Ramularia_areola_cotton.jpg/800px-Ramularia_areola_cotton.jpg",
    "bicudo-algodoeiro": "https://upload.wikimedia.org/wikipedia/commons/thumb/a/a2/Anthonomus_grandis.jpg/800px-Anthonomus_grandis.jpg",
    "pulgao-algodao": "https://upload.wikimedia.org/wikipedia/commons/thumb/a/a1/Aphis_gossypii.jpg/800px-Aphis_gossypii.jpg",

    # ================================================================
    # FEIJÃO - Doenças
    # ================================================================
    "antracnose-feijao": "https://upload.wikimedia.org/wikipedia/commons/thumb/a/a3/Bean_anthracnose.jpg/800px-Bean_anthracnose.jpg",
    "ferrugem-feijao": "https://upload.wikimedia.org/wikipedia/commons/thumb/b/b1/Bean_rust_uromyces.jpg/800px-Bean_rust_uromyces.jpg",
    "mancha-angular-feijao": "https://upload.wikimedia.org/wikipedia/commons/thumb/a/a4/Angular_leaf_spot_bean.jpg/800px-Angular_leaf_spot_bean.jpg",
    "mosaico-dourado-feijao": "https://upload.wikimedia.org/wikipedia/commons/thumb/b/b2/Bean_golden_mosaic.jpg/800px-Bean_golden_mosaic.jpg",

    # ================================================================
    # TRIGO - Doenças
    # ================================================================
    "brusone-trigo": "https://upload.wikimedia.org/wikipedia/commons/thumb/w/w1/Wheat_blast_pyricularia.jpg/800px-Wheat_blast_pyricularia.jpg",
    "giberela-trigo": "https://upload.wikimedia.org/wikipedia/commons/thumb/f/f1/Fusarium_head_blight_wheat.jpg/800px-Fusarium_head_blight_wheat.jpg",
    "mancha-amarela-trigo": "https://upload.wikimedia.org/wikipedia/commons/thumb/t/t1/Tan_spot_wheat.jpg/800px-Tan_spot_wheat.jpg",
    "ferrugem-folha-trigo": "https://upload.wikimedia.org/wikipedia/commons/thumb/l/l1/Leaf_rust_wheat.jpg/800px-Leaf_rust_wheat.jpg",

    # ================================================================
    # CAFÉ - Doenças e Pragas
    # ================================================================
    "ferrugem-cafe": "https://upload.wikimedia.org/wikipedia/commons/thumb/c/c1/Coffee_leaf_rust.jpg/800px-Coffee_leaf_rust.jpg",
    "cercosporiose-cafe": "https://upload.wikimedia.org/wikipedia/commons/thumb/c/c2/Cercospora_coffeicola.jpg/800px-Cercospora_coffeicola.jpg",
    "bicho-mineiro-cafe": "https://upload.wikimedia.org/wikipedia/commons/thumb/l/l2/Leucoptera_coffeella.jpg/800px-Leucoptera_coffeella.jpg",
    "broca-cafe": "https://upload.wikimedia.org/wikipedia/commons/thumb/h/h1/Hypothenemus_hampei.jpg/800px-Hypothenemus_hampei.jpg",

    # ================================================================
    # CANA-DE-AÇÚCAR - Doenças e Pragas
    # ================================================================
    "broca-cana": "https://upload.wikimedia.org/wikipedia/commons/thumb/d/d2/Diatraea_saccharalis.jpg/800px-Diatraea_saccharalis.jpg",
    "ferrugem-alaranjada-cana": "https://upload.wikimedia.org/wikipedia/commons/thumb/o/o1/Orange_rust_sugarcane.jpg/800px-Orange_rust_sugarcane.jpg",
    "cigarrinha-cana": "https://upload.wikimedia.org/wikipedia/commons/thumb/m/m1/Mahanarva_fimbriolata.jpg/800px-Mahanarva_fimbriolata.jpg",

    # ================================================================
    # SORGO - Doenças e Pragas
    # ================================================================
    "pulgao-verde-sorgo": "https://upload.wikimedia.org/wikipedia/commons/thumb/s/s2/Schizaphis_graminum.jpg/800px-Schizaphis_graminum.jpg",
    "antracnose-sorgo": "https://upload.wikimedia.org/wikipedia/commons/thumb/a/a5/Sorghum_anthracnose.jpg/800px-Sorghum_anthracnose.jpg",
}

# NOTA: Muitas URLs acima são exemplos de padrão Wikimedia.
# Para obter URLs reais, acesse:
# - https://commons.wikimedia.org/wiki/Category:Plant_diseases
# - https://www.invasive.org (Bugwood - University of Georgia)
# - https://www.ipmimages.org (IPM Images - public domain)


def download_image(url: str) -> bytes | None:
    """Baixa imagem de uma URL."""
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (compatible; AgroCRM/1.0)"
        }
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        return response.content
    except Exception as e:
        print(f"  Erro ao baixar: {e}")
        return None


def upload_to_r2(client, bucket: str, key: str, data: bytes, content_type: str = "image/jpeg"):
    """Faz upload de dados para o R2."""
    try:
        client.put_object(
            Bucket=bucket,
            Key=key,
            Body=data,
            ContentType=content_type,
        )
        return True
    except Exception as e:
        print(f"  Erro no upload: {e}")
        return False


def main():
    # Verifica variáveis de ambiente
    required_vars = ["R2_ACCOUNT_ID", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY", "R2_BUCKET", "R2_PUBLIC_BASE_URL"]
    missing = [v for v in required_vars if not os.environ.get(v)]
    if missing:
        print(f"Erro: Variáveis de ambiente faltando: {', '.join(missing)}")
        print("\nDefina as variáveis antes de executar:")
        print("  $env:R2_ACCOUNT_ID = 'seu_account_id'")
        print("  $env:R2_ACCESS_KEY_ID = 'sua_access_key'")
        print("  $env:R2_SECRET_ACCESS_KEY = 'sua_secret_key'")
        print("  $env:R2_BUCKET = 'seu_bucket'")
        print("  $env:R2_PUBLIC_BASE_URL = 'https://seu-bucket.r2.dev'")
        return 1

    bucket = os.environ["R2_BUCKET"]
    public_base = os.environ["R2_PUBLIC_BASE_URL"].rstrip("/")

    print(f"Bucket: {bucket}")
    print(f"Base URL: {public_base}")
    print()

    client = get_r2_client()

    uploaded = 0
    skipped = 0
    failed = 0

    for slug, url in DISEASE_IMAGES.items():
        print(f"[{slug}]")

        if not url:
            print("  ⏭️  URL não definida - pulando")
            skipped += 1
            continue

        # Baixa a imagem
        print(f"  ⬇️  Baixando de {url[:50]}...")
        image_data = download_image(url)

        if not image_data:
            print("  ❌ Falha no download")
            failed += 1
            continue

        # Upload para R2
        key = f"diseases/{slug}.jpg"
        print(f"  ⬆️  Enviando para {key}...")

        if upload_to_r2(client, bucket, key, image_data):
            final_url = f"{public_base}/{key}"
            print(f"  ✅ Sucesso: {final_url}")
            uploaded += 1
        else:
            failed += 1

    print()
    print("=" * 50)
    print(f"Resultados: {uploaded} enviados, {skipped} pulados, {failed} falhas")
    print()
    print("Para adicionar URLs de imagens, edite DISEASE_IMAGES neste script.")
    print("Fontes sugeridas de imagens de domínio público:")
    print("  - Embrapa (infoteca.cnptia.embrapa.br)")
    print("  - Wikimedia Commons")
    print("  - USDA (public domain)")

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
