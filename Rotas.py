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

def get_coords(address):
    url = f"https://api.opencagedata.com/geocode/v1/json?q={address}&key={OPENCAGE_KEY}&language=pt&countrycode=br"
    response = requests.get(url).json()
    if response.get('results'):
        coords = response['results'][0]['geometry']
        return coords['lat'], coords['lng']
    return None, None

def calcular_rota(coords, tempo_atendimento=1800, jornada=28800):
    url = "https://api.openrouteservice.org/v2/directions/driving-car"
    headers = {"Authorization": ORS_KEY, "Content-Type": "application/json"}
    body = {"coordinates": [[lon, lat] for lat, lon in coords if lat and lon]}
    response = requests.post(url, json=body, headers=headers).json()

    if "routes" not in response or not response["routes"]:
        return [], {}, []

    rota = response['routes'][0]
    props = rota['segments'][0]
    distancia_km = props['distance'] / 1000
    tempo_seg = props['duration']

    geometry = convert.decode_polyline(rota['geometry'])

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

uploaded_file = st.file_uploader("Carregue o arquivo de rotas", type=["xlsx"])

if uploaded_file is not None:
    df = pd.read_excel(uploaded_file)

    if "Latitude" not in df.columns or "Longitude" not in df.columns:
        progress = st.progress(0)
        latitudes, longitudes = [], []
        for i, endereco in enumerate(df['Endereço']):
            lat, lon = get_coords(endereco)
            latitudes.append(lat)
            longitudes.append(lon)
            progress.progress((i+1)/len(df))
        df['Latitude'] = latitudes
        df['Longitude'] = longitudes

    invalidos = df[df['Latitude'].isna() | df['Longitude'].isna()]
    if not invalidos.empty:
        st.warning("⚠️ Alguns endereços não foram localizados. Corrija manualmente:")
        for idx, row in invalidos.iterrows():
            coord_str = st.text_input(f"Coordenadas (lat, lon) para {row['Cliente']}", key=f"coord_{idx}")
            if coord_str:
                try:
                    lat_str, lon_str = coord_str.split(",")
                    df.at[idx, 'Latitude'] = float(lat_str.strip())
                    df.at[idx, 'Longitude'] = float(lon_str.strip())
                    st.success(f"✅ Coordenadas salvas para {row['Cliente']}")
                except:
                    st.error("Formato inválido. Use: lat, lon")

    dia = st.selectbox("Selecione o dia", df['Dias de visita'].unique())
    motorista = st.selectbox("Selecione o motorista", df['Motorista'].unique())
    veiculo = st.selectbox("Selecione o veículo", df['Veículo'].unique())

    if st.button("Atualizar rotas"):
        dados_filtrados = df[(df['Dias de visita'].str.contains(dia)) &
                             (df['Motorista'] == motorista) &
                             (df['Veículo'] == veiculo)]

        coords_original = [(lat, lon) for lat, lon in zip(dados_filtrados['Latitude'], dados_filtrados['Longitude'])
                           if pd.notna(lat) and pd.notna(lon)]

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
            st.error("Nenhuma coordenada válida disponível.")
else:
    st.warning("Por favor, carregue o arquivo de rotas (.xlsx).")


# In[ ]:




