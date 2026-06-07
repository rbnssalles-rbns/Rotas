#!/usr/bin/env python
# coding: utf-8

# In[1]:


import pandas as pd
import requests
import streamlit as st
from datetime import timedelta
from itertools import permutations

ORS_KEY = "eyJvcmciOiI1YjNjZTM1OTc4NTExMTAwMDFjZjYyNDgiLCJpZCI6IjI5ZTlmZjk3ZTg4MzZjZGM1MDc3ZjBlMjNjOWMyYWU5YjM4ZTNhNzFjYTU4YzYxYjRhM2FmNjY0IiwiaCI6Im11cm11cjY0In0="
OPENCAGE_KEY = "480d28fce0a04bd4839c8cc832201807"

# Função para geocodificação com OpenCage
def get_coords(address):
    url = f"https://api.opencagedata.com/geocode/v1/json?q={address}&key={OPENCAGE_KEY}&language=pt&countrycode=br"
    response = requests.get(url).json()
    if response.get('results'):
        coords = response['results'][0]['geometry']
        lat, lon = coords['lat'], coords['lng']
        # Debug: mostrar resultado da geocodificação
        st.write(f"Endereço: {address} → Coordenadas: {lat}, {lon}")
        return lat, lon
    else:
        st.error(f"❌ Endereço não localizado pelo OpenCage: {address}")
        return None, None

# Função para calcular rota completa via OpenRouteService
def calcular_rota(coords, tempo_atendimento=1800, jornada=28800):
    url = "https://api.openrouteservice.org/v2/directions/driving-car"
    headers = {"Authorization": ORS_KEY, "Content-Type": "application/json"}
    # ORS exige [longitude, latitude]
    body = {"coordinates": [[lon, lat] for lat, lon in coords if lat and lon]}

    # Debug: mostrar coordenadas enviadas para ORS
    st.write("📤 Coordenadas enviadas para ORS:", body)

    response = requests.post(url, json=body, headers=headers).json()

    if "routes" not in response or not response["routes"]:
        st.error("❌ ORS não retornou rotas. Verifique coordenadas enviadas acima.")
        return [], {}, []

    rota = response['routes'][0]
    geometry = rota['geometry']
    props = rota['segments'][0]

    # Debug: mostrar resumo da resposta ORS
    st.write("📥 Resposta ORS (resumida):", {
        "distância_m": props['distance'],
        "duração_s": props['duration'],
        "pontos_geom": len(geometry['coordinates'])
    })

    distancia_km = props['distance'] / 1000
    tempo_seg = props['duration']

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

    return tabela_de_para, capacidade, geometry

# Função simples de otimização (permutações - apenas para poucas rotas)
def otimizar_rota(coords):
    melhor_rota = None
    menor_distancia = float("inf")
    for perm in permutations(coords):
        body = {"coordinates": [[lon, lat] for lat, lon in perm]}
        url = "https://api.openrouteservice.org/v2/directions/driving-car"
        headers = {"Authorization": ORS_KEY, "Content-Type": "application/json"}
        response = requests.post(url, json=body, headers=headers).json()
        if "routes" not in response:
            continue
        dist_total = response['routes'][0]['segments'][0]['distance'] / 1000
        if dist_total < menor_distancia:
            menor_distancia = dist_total
            melhor_rota = perm
    return list(melhor_rota) if melhor_rota else coords

# Upload do arquivo Excel
uploaded_file = st.file_uploader("Carregue o arquivo de rotas", type=["xlsx"])

if uploaded_file is not None:
    df = pd.read_excel(uploaded_file)

    # Geocodificação com debug
    if "Latitude" not in df.columns or "Longitude" not in df.columns:
        latitudes, longitudes = [], []
        for endereco in df['Endereço']:
            lat, lon = get_coords(endereco)
            latitudes.append(lat)
            longitudes.append(lon)
        df['Latitude'] = latitudes
        df['Longitude'] = longitudes

    # Botão para recalcular rotas
    if st.button("Atualizar rotas"):
        dados_filtrados = df[(df['Latitude'].notna()) & (df['Longitude'].notna())]
        coords_original = [(lat, lon) for lat, lon in zip(dados_filtrados['Latitude'], dados_filtrados['Longitude'])]

        if coords_original:
            # --- Rota Original ---
            tabela_de_para_orig, capacidade_orig, rota_coords_orig = calcular_rota(coords_original)
            st.subheader("Rota Original")
            st.dataframe(pd.DataFrame(tabela_de_para_orig))
            st.dataframe(pd.DataFrame([capacidade_orig]))

            # --- Rota Otimizada ---
            coords_otimizada = otimizar_rota(coords_original)
            tabela_de_para_otim, capacidade_otim, rota_coords_otim = calcular_rota(coords_otimizada)
            st.subheader("Rota Otimizada")
            st.dataframe(pd.DataFrame(tabela_de_para_otim))
            st.dataframe(pd.DataFrame([capacidade_otim]))
        else:
            st.error("Nenhuma coordenada válida disponível para calcular a rota.")
else:
    st.warning("Por favor, carregue o arquivo de rotas (.xlsx).")


# In[ ]:




