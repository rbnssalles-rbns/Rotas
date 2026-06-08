#!/usr/bin/env python
# coding: utf-8

# In[1]:


import pandas as pd
import requests
import streamlit as st
from datetime import timedelta
from itertools import permutations
from openrouteservice import convert
import pydeck as pdk

ORS_KEY = "eyJvcmciOiI1YjNjZTM1OTc4NTExMTAwMDFjZjYyNDgiLCJpZCI6IjI5ZTlmZjk3ZTg4MzZjZGM1MDc3ZjBlMjNjOWMyYWU5YjM4ZTNhNzFjYTU4YzYxYjRhM2FmNjY0IiwiaCI6Im11cm11cjY0In0="
OPENCAGE_KEY = "480d28fce0a04bd4839c8cc832201807"

# -------------------------------
# Aparência: tamanho e cor dos marcadores
# -------------------------------
st.sidebar.header("🎨 Aparência do mapa")
icon_size = st.sidebar.slider("Tamanho do marcador (1–8)", min_value=1, max_value=8, value=4)
size_scale = st.sidebar.slider("Escala do marcador (5–30)", min_value=5, max_value=30, value=15)

color_option = st.sidebar.selectbox(
    "Cor dos clientes",
    ["Azul", "Verde", "Laranja", "Roxo", "Cinza"]
)

# URLs de ícones (Leaflet color markers 2x PNG)
marker_urls = {
    "Azul":   "https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-2x-blue.png",
    "Verde":  "https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-2x-green.png",
    "Laranja":"https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-2x-orange.png",
    "Roxo":   "https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-2x-violet.png",
    "Cinza":  "https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-2x-grey.png",
}
client_marker_url = marker_urls[color_option]
cd_marker_url = "https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-2x-red.png"  # vermelho fixo

# Geocodificação com OpenCage
def get_coords(address):
    url = f"https://api.opencagedata.com/geocode/v1/json?q={address}&key={OPENCAGE_KEY}&language=pt&countrycode=br"
    response = requests.get(url).json()
    if response.get('results'):
        coords = response['results'][0]['geometry']
        lat, lon = coords['lat'], coords['lng']
        st.write(f"Endereço: {address} → Coordenadas: {lat}, {lon}")
        return lat, lon
    else:
        st.error(f"❌ Endereço não localizado pelo OpenCage: {address}")
        return None, None

# Cálculo da rota com distâncias reais entre pares
def calcular_rota(coords, tempo_atendimento=1800, jornada=28800):
    url = "https://api.openrouteservice.org/v2/directions/driving-car"
    headers = {"Authorization": ORS_KEY, "Content-Type": "application/json"}
    tabela_de_para = []
    distancia_total = 0
    tempo_total = 0
    geometry_coords = []

    for i in range(len(coords) - 1):
        lat1, lon1 = coords[i]
        lat2, lon2 = coords[i + 1]
        body = {"coordinates": [[lon1, lat1], [lon2, lat2]]}
        response = requests.post(url, json=body, headers=headers).json()

        if "routes" not in response:
            st.warning(f"⚠️ Falha no trecho {i} → {i+1}")
            continue

        rota = response["routes"][0]
        props = rota["segments"][0]
        distancia_km = props["distance"] / 1000
        tempo_min = props["duration"] / 60
        distancia_total += props["distance"]
        tempo_total += props["duration"]

        # Decodificar geometria do trecho
        geom = convert.decode_polyline(rota["geometry"])
        geometry_coords.extend(geom["coordinates"])

        tabela_de_para.append({
            "De": f"Cliente {i}" if i > 0 else "Origem",
            "Para": f"Cliente {i + 1}",
            "Distância (km)": round(distancia_km, 2),
            "Tempo (min)": round(tempo_min, 2)
        })

    total_tempo = tempo_total + len(coords) * tempo_atendimento
    capacidade = {
        "Clientes atendidos": len(coords),
        "Distância total (km)": round(distancia_total / 1000, 2),
        "Tempo total (HH:MM:SS)": str(timedelta(seconds=int(total_tempo))),
        "Status jornada": "Dentro da jornada" if total_tempo <= jornada else "Fora da jornada"
    }

    return tabela_de_para, capacidade, geometry_coords

# Visualização Pydeck com ícones estilo Google Maps
def mostrar_rota(coords, geometry, titulo, cor, client_marker_url, cd_marker_url, icon_size, size_scale):
    if not geometry:
        st.error(f"❌ Não há geometria para {titulo}")
        return

    icon_data = []
    for i, (lat, lon) in enumerate(coords):
        icon_data.append({
            "lat": lat,
            "lon": lon,
            "cliente": f"Cliente {i}" if i > 0 else "Origem",
            "icon_data": {
                "url": client_marker_url if i > 0 else cd_marker_url,
                "width": 128,
                "height": 128,
                "anchorY": 128
            }
        })

    icon_layer = pdk.Layer(
        "IconLayer",
        data=icon_data,
        get_icon="icon_data",
        get_size=icon_size,
        size_scale=size_scale,
        get_position=["lon", "lat"],
        pickable=True
    )

    path_layer = pdk.Layer(
        "PathLayer",
        data=[{"path": [[lon, lat] for lon, lat in geometry]}],
        get_color=cor,
        width_scale=2,
        width_min_pixels=2
    )

    view_state = pdk.ViewState(latitude=coords[0][0], longitude=coords[0][1], zoom=13)
    deck = pdk.Deck(layers=[icon_layer, path_layer], initial_view_state=view_state, tooltip={"text": "{cliente}"})
    st.pydeck_chart(deck)

# Upload do arquivo Excel
uploaded_file = st.file_uploader("Carregue o arquivo de rotas", type=["xlsx"])

if uploaded_file is not None:
    df = pd.read_excel(uploaded_file)

    # Geocodificação
    latitudes, longitudes = [], []
    for endereco in df['Endereço']:
        lat, lon = get_coords(endereco)
        latitudes.append(lat)
        longitudes.append(lon)
    df['Latitude'] = latitudes
    df['Longitude'] = longitudes

    if st.button("Atualizar rotas"):
        dados_filtrados = df[(df['Latitude'].notna()) & (df['Longitude'].notna())]
        coords_original = [(lat, lon) for lat, lon in zip(dados_filtrados['Latitude'], dados_filtrados['Longitude'])]

        if coords_original and len(coords_original) >= 2:
            # Rota Original
            tabela_orig, capacidade_orig, rota_orig = calcular_rota(coords_original)
            st.subheader("Rota Original")
            st.write("➡️ DE → PARA")
            st.dataframe(pd.DataFrame(tabela_orig))
            st.write("📊 Capacidade")
            st.dataframe(pd.DataFrame([capacidade_orig]))
            mostrar_rota(coords_original, rota_orig, "Rota Original", [0, 0, 255],
                         client_marker_url, cd_marker_url, icon_size, size_scale)

            # Rota Otimizada (exemplo simples: invertida)
            tabela_otim, capacidade_otim, rota_otim = calcular_rota(coords_original[::-1])
            st.subheader("Rota Otimizada")
            st.write("➡️ DE → PARA")
            st.dataframe(pd.DataFrame(tabela_otim))
            st.write("📊 Capacidade")
            st.dataframe(pd.DataFrame([capacidade_otim]))
            mostrar_rota(coords_original[::-1], rota_otim, "Rota Otimizada", [255, 0, 0],
                         client_marker_url, cd_marker_url, icon_size, size_scale)
        else:
            st.error("Necessário pelo menos dois pontos válidos para calcular a rota.")
else:
    st.warning("Por favor, carregue o arquivo de rotas (.xlsx).")


# In[ ]:




