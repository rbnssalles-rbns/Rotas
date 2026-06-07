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
    body = {"coordinates": [[c[1], c[0]] for c in coords if c[0] and c[1]]}
    response = requests.post(url, json=body, headers=headers).json()

    if "routes" not in response or not response["routes"]:
        st.error("Não foi possível calcular a rota. Verifique os endereços ou coordenadas.")
        return [], {}, []

    # Extraindo corretamente da estrutura atual da API
    geometry = response['routes'][0]['geometry']['coordinates']
    props = response['routes'][0]['segments'][0]
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

    # Geocodificação com barra de progresso
    if "Latitude" not in df.columns or "Longitude" not in df.columns:
        progress = st.progress(0)
        total = len(df)
        latitudes, longitudes = [], []
        for i, endereco in enumerate(df['Endereço']):
            with st.spinner(f"Geocodificando endereço {i+1}/{total}..."):
                lat, lon = get_coords(endereco)
                latitudes.append(lat)
                longitudes.append(lon)
            progress.progress((i+1)/total)
        df['Latitude'] = latitudes
        df['Longitude'] = longitudes

    # Sinalizar endereços não encontrados com campo único
    invalidos = df[df['Latitude'].isna() | df['Longitude'].isna()]
    if not invalidos.empty:
        st.warning("⚠️ Alguns endereços não foram localizados pelo OpenCage. Corrija manualmente antes de atualizar as rotas:")
        for idx, row in invalidos.iterrows():
            st.error(f"Endereço não encontrado: **{row['Cliente']}** — {row['Endereço']}")
            coord_str = st.text_input(
                f"Coordenadas (lat, lon) para {row['Cliente']}",
                value="",
                key=f"coord_{idx}"
            )
            if coord_str:
                try:
                    lat_str, lon_str = coord_str.split(",")
                    lat, lon = float(lat_str.strip()), float(lon_str.strip())
                    df.at[idx, 'Latitude'] = lat
                    df.at[idx, 'Longitude'] = lon
                    st.success(f"✅ Coordenadas salvas para {row['Cliente']}")
                except Exception:
                    st.error("Formato inválido. Use: lat, lon (exemplo: -3.732, -38.527)")

    # Filtros sincronizados
    dia = st.selectbox("Selecione o dia", df['Dias de visita'].unique())
    motorista = st.selectbox("Selecione o motorista", df['Motorista'].unique())
    veiculo = st.selectbox("Selecione o veículo", df['Veículo'].unique())

    # Botão para recalcular rotas
    if st.button("Atualizar rotas"):
        with st.spinner("Calculando rotas..."):
            dados_filtrados = df[(df['Dias de visita'].str.contains(dia)) &
                                 (df['Motorista'] == motorista) &
                                 (df['Veículo'] == veiculo)]

            coords_original = [(lat, lon) for lat, lon in zip(dados_filtrados['Latitude'], dados_filtrados['Longitude'])
                               if pd.notna(lat) and pd.notna(lon)]

            if coords_original:
                # --- Rota Original ---
                tabela_de_para_orig, capacidade_orig, rota_coords_orig = calcular_rota(coords_original)
                st.subheader(f"Rota Original ({motorista} - {veiculo})")
                st.dataframe(pd.DataFrame(tabela_de_para_orig))
                st.dataframe(pd.DataFrame([capacidade_orig]))

                # --- Rota Otimizada ---
                coords_otimizada = otimizar_rota(coords_original)
                tabela_de_para_otim, capacidade_otim, rota_coords_otim = calcular_rota(coords_otimizada)
                st.subheader(f"Rota Otimizada ({motorista} - {veiculo})")
                st.dataframe(pd.DataFrame(tabela_de_para_otim))
                st.dataframe(pd.DataFrame([capacidade_otim]))
            else:
                st.error("Nenhuma coordenada válida disponível para calcular a rota.")
else:
    st.warning("Por favor, carregue o arquivo de rotas (.xlsx).")


# In[ ]:




