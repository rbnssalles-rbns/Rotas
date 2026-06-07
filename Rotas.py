#!/usr/bin/env python
# coding: utf-8

# In[1]:


import pandas as pd
import requests
import streamlit as st
import pydeck as pdk
from datetime import timedelta
from itertools import permutations

ORS_KEY = "eyJvcmciOiI1YjNjZTM1OTc4NTExMTAwMDFjZjYyNDgiLCJpZCI6IjI5ZTlmZjk3ZTg4MzZjZGM1MDc3ZjBlMjNjOWMyYWU5YjM4ZTNhNzFjYTU4YzYxYjRhM2FmNjY0IiwiaCI6Im11cm11cjY0In0="
OPENCAGE_KEY = "480d28fce0a04bd4839c8cc832201807"

# Função para geocodificação com OpenCage
def get_coords(address):
    url = f"https://api.opencagedata.com/geocode/v1/json?q={address}&key={OPENCAGE_KEY}&language=pt&countrycode=br"
    response = requests.get(url).json()
    if response['results']:
        coords = response['results'][0]['geometry']
        return coords['lat'], coords['lng']
    else:
        return None, None

# Função para calcular rota completa via OpenRouteService
def calcular_rota(coords, tempo_atendimento=1800, jornada=28800):
    url = "https://api.openrouteservice.org/v2/directions/driving-car"
    headers = {"Authorization": ORS_KEY, "Content-Type": "application/json"}
    body = {"coordinates": [[c[1], c[0]] for c in coords]}
    response = requests.post(url, json=body, headers=headers).json()

    geometry = response['features'][0]['geometry']['coordinates']
    props = response['features'][0]['properties']['segments'][0]
    distancia_km = props['distance'] / 1000
    tempo_seg = props['duration']

    tabela_de_para = []
    for i in range(len(coords)-1):
        tabela_de_para.append({
            "De": f"Cliente {i}" if i>0 else "Origem",
            "Para": f"Cliente {i+1}",
            "Distância (km)": round(distancia_km / (len(coords)-1), 2),
            "Tempo (min)": round((tempo_seg / 60) / (len(coords)-1), 2)
        })

    total_tempo = tempo_seg + len(coords) * tempo_atendimento
    capacidade = {
        "Clientes atendidos": len(coords),
        "Distância total (km)": round(distancia_km, 2),
        "Tempo total (HH:MM:SS)": str(timedelta(seconds=int(total_tempo))),
        "Status jornada": "Dentro da jornada" if total_tempo <= jornada else "Fora da jornada"
    }

    return tabela_de_para, capacidade, geometry

# Função simples de otimização (permutações - apenas para poucas rotas)
def otimizar_rota(coords):
    melhor_rota = None
    menor_distancia = float("inf")
    for perm in permutations(coords):
        body = {"coordinates": [[c[1], c[0]] for c in perm]}
        url = "https://api.openrouteservice.org/v2/directions/driving-car"
        headers = {"Authorization": ORS_KEY, "Content-Type": "application/json"}
        response = requests.post(url, json=body, headers=headers).json()
        dist_total = response['features'][0]['properties']['segments'][0]['distance'] / 1000
        if dist_total < menor_distancia:
            menor_distancia = dist_total
            melhor_rota = perm
    return list(melhor_rota)

# Upload do arquivo Excel
uploaded_file = st.file_uploader("Carregue o arquivo de rotas", type=["xlsx"])

if uploaded_file is not None:
    df = pd.read_excel(uploaded_file)

    # Gerar coordenadas via OpenCage
    if "Latitude" not in df.columns or "Longitude" not in df.columns:
        df[['Latitude','Longitude']] = df['Endereço'].apply(lambda x: pd.Series(get_coords(x)))

    # Filtros sincronizados
    dia = st.selectbox("Selecione o dia", df['Dias de visita'].unique())
    motorista = st.selectbox("Selecione o motorista", df['Motorista'].unique())
    veiculo = st.selectbox("Selecione o veículo", df['Veículo'].unique())

    dados_filtrados = df[(df['Dias de visita'].str.contains(dia)) &
                         (df['Motorista'] == motorista) &
                         (df['Veículo'] == veiculo)]

    coords_original = list(zip(dados_filtrados['Latitude'], dados_filtrados['Longitude']))

    # --- Rota Original ---
    tabela_de_para_orig, capacidade_orig, rota_coords_orig = calcular_rota(coords_original)

    st.subheader(f"Rota Original ({motorista} - {veiculo})")
    rota_data_orig = [{"path": [[lon, lat] for lon, lat in rota_coords_orig], "color": [0, 128, 255]}]
    marcadores_orig = [{"position": [c[1], c[0]], "Cliente": nome}
                       for c, nome in zip(coords_original, dados_filtrados['Cliente'])]

    st.pydeck_chart(pdk.Deck(
        map_style="mapbox://styles/mapbox/dark-v10",
        layers=[
            pdk.Layer("PathLayer",
                      data=rota_data_orig,
                      get_path="path",
                      get_color="color",
                      width_scale=2,
                      width_min_pixels=2),
            pdk.Layer("ScatterplotLayer",
                      data=marcadores_orig,
                      get_position="position",
                      get_radius=80,
                      get_color=[255, 255, 0],
                      pickable=True)
        ],
        initial_view_state=pdk.ViewState(
            latitude=coords_original[0][0],
            longitude=coords_original[0][1],
            zoom=12
        ),
        tooltip={"text": "{Cliente}"}
    ))
    st.write("Tabela DE → PARA (Original)")
    st.dataframe(pd.DataFrame(tabela_de_para_orig))
    st.write("Tabela de Capacidade (Original)")
    st.dataframe(pd.DataFrame([capacidade_orig]))

    # --- Rota Otimizada ---
    coords_otimizada = otimizar_rota(coords_original)
    tabela_de_para_otim, capacidade_otim, rota_coords_otim = calcular_rota(coords_otimizada)

    st.subheader(f"Rota Otimizada ({motorista} - {veiculo})")
    rota_data_otim = [{"path": [[lon, lat] for lon, lat in rota_coords_otim], "color": [255, 0, 0]}]
    marcadores_otim = [{"position": [c[1], c[0]], "Cliente": nome}
                       for c, nome in zip(coords_otimizada, dados_filtrados['Cliente'])]

    st.pydeck_chart(pdk.Deck(
        map_style="mapbox://styles/mapbox/dark-v10",
        layers=[
            pdk.Layer("PathLayer",
                      data=rota_data_otim,
                      get_path="path",
                      get_color="color",
                      width_scale=2,
                      width_min_pixels=2),
            pdk.Layer("ScatterplotLayer",
                      data=marcadores_otim,
                      get_position="position",
                      get_radius=80,
                      get_color=[0, 255, 0],
                      pickable=True)
        ],
        initial_view_state=pdk.ViewState(
            latitude=coords_otimizada[0][0],
            longitude=coords_otimizada[0][1],
            zoom=12
        ),
        tooltip={"text": "{Cliente}"}
    ))
    st.write("Tabela DE → PARA (Otimizada)")
    st.dataframe(pd.DataFrame(tabela_de_para_otim))
    st.write("Tabela de Capacidade (Otimizada)")
    st.dataframe(pd.DataFrame([capacidade_otim]))
else:
    st.warning("Por favor, carregue o arquivo de rotas (.xlsx).")


# In[ ]:




