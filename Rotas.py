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

# Geocodificação com OpenCage (mantém debug)
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

# Cálculo da rota com ORS
def calcular_rota(coords, tempo_atendimento=1800, jornada=28800):
    url = "https://api.openrouteservice.org/v2/directions/driving-car"
    headers = {"Authorization": ORS_KEY, "Content-Type": "application/json"}
    body = {"coordinates": [[lon, lat] for lat, lon in coords if lat and lon]}
    st.write("📤 Coordenadas enviadas para ORS:", body)

    response = requests.post(url, json=body, headers=headers).json()

    if "routes" not in response or not response["routes"]:
        st.error("❌ ORS não retornou rotas. Verifique coordenadas enviadas acima.")
        return [], {}, []

    rota = response['routes'][0]
    props = rota['segments'][0]
    distancia_km = props['distance'] / 1000
    tempo_seg = props['duration']

    geometry = convert.decode_polyline(rota['geometry'])
    st.write("📥 Resposta ORS (resumida):", {
        "distância_m": props['distance'],
        "duração_s": props['duration'],
        "pontos_geom": len(geometry['coordinates'])
    })

    tabela_de_para = []
    for i in range(len(coords) - 1):
        tabela_de_para.append({
            "De": f"Cliente {i}" if i > 0 else "Origem",
            "Para": f"Cliente {i + 1}",
            "Distância (km)": round(distancia_km / (len(coords) - 1), 2),
            "Tempo (min)": round((tempo_seg / 60) / (len(coords) - 1), 2)
        })

    total_tempo = tempo_seg + len(coords) * tempo_atendimento
    capacidade = {
        "Clientes atendidos": len(coords),
        "Distância total (km)": round(distancia_km, 2),
        "Tempo total (HH:MM:SS)": str(timedelta(seconds=int(total_tempo))),
        "Status jornada": "Dentro da jornada" if total_tempo <= jornada else "Fora da jornada"
    }

    return tabela_de_para, capacidade, geometry['coordinates']

# Visualização Pydeck
def mostrar_rota(coords, geometry, titulo, cor):
    if not geometry:
        st.error(f"❌ Não há geometria para {titulo}")
        return

    scatter = pdk.Layer(
        "ScatterplotLayer",
        data=[{"lat": lat, "lon": lon, "cliente": f"Cliente {i}"} for i, (lat, lon) in enumerate(coords)],
        get_position=["lon", "lat"],
        get_color=cor,
        get_radius=150,
        pickable=True
    )

    path = pdk.Layer(
        "PathLayer",
        data=[{"path": [[lon, lat] for lon, lat in geometry]}],
        get_color=cor,
        width_scale=2,
        width_min_pixels=2
    )

    view_state = pdk.ViewState(latitude=coords[0][0], longitude=coords[0][1], zoom=12)
    deck = pdk.Deck(layers=[scatter, path], initial_view_state=view_state, tooltip={"text": "{cliente}"})
    st.pydeck_chart(deck)

# Upload do arquivo Excel
uploaded_file = st.file_uploader("Carregue o arquivo de rotas", type=["xlsx"])

if uploaded_file is not None:
    df = pd.read_excel(uploaded_file)

    # Geocodificação com debug e verificação
    st.write("🔍 Verificando endereços via OpenCage...")
    latitudes, longitudes, status = [], [], []
    for endereco in df['Endereço']:
        lat, lon = get_coords(endereco)
        latitudes.append(lat)
        longitudes.append(lon)
        status.append("✅ Localizado" if lat and lon else "❌ Não localizado")
    df['Latitude'] = latitudes
    df['Longitude'] = longitudes
    df['Status Geocodificação'] = status

    st.write("📋 Resultado da geocodificação:")
    st.dataframe(df[['Endereço', 'Latitude', 'Longitude', 'Status Geocodificação']])

    # Filtrar apenas coordenadas válidas
    dados_filtrados = df[(df['Latitude'].notna()) & (df['Longitude'].notna())]
    coords_original = [(lat, lon) for lat, lon in zip(dados_filtrados['Latitude'], dados_filtrados['Longitude'])]

    if st.button("Atualizar rotas"):
        if coords_original:
            # Rota Original
            tabela_orig, capacidade_orig, rota_orig = calcular_rota(coords_original)
            st.subheader("Rota Original")
            st.write("➡️ DE → PARA")
            st.dataframe(pd.DataFrame(tabela_orig))
            st.write("📊 Capacidade")
            st.dataframe(pd.DataFrame([capacidade_orig]))
            mostrar_rota(coords_original, rota_orig, "Rota Original", [0, 0, 255])

            # Rota Otimizada (exemplo simples: invertida)
            tabela_otim, capacidade_otim, rota_otim = calcular_rota(coords_original[::-1])
            st.subheader("Rota Otimizada")
            st.write("➡️ DE → PARA")
            st.dataframe(pd.DataFrame(tabela_otim))
            st.write("📊 Capacidade")
            st.dataframe(pd.DataFrame([capacidade_otim]))
            mostrar_rota(coords_original[::-1], rota_otim, "Rota Otimizada", [255, 0, 0])
        else:
            st.error("Nenhuma coordenada válida disponível para calcular a rota.")
else:
    st.warning("Por favor, carregue o arquivo de rotas (.xlsx).")


# In[ ]:




