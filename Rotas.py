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

# Função para geocodificação
def get_coords(address):
    url = f"https://api.opencagedata.com/geocode/v1/json?q={address}&key={OPENCAGE_KEY}"
    response = requests.get(url).json()
    coords = response['results'][0]['geometry']
    return coords['lat'], coords['lng']

# Função para calcular segmento entre dois pontos
def calcular_segmento(origem, destino):
    body = {"coordinates": [[origem[1], origem[0]], [destino[1], destino[0]]]}
    url = "https://api.openrouteservice.org/v2/directions/driving-car"
    headers = {"Authorization": ORS_KEY}
    response = requests.post(url, json=body, headers=headers).json()
    seg = response['features'][0]['properties']['segments'][0]
    return seg['distance']/1000, seg['duration'], response['features'][0]['geometry']['coordinates']

# Função para calcular rota completa
def calcular_rota(coords, tempo_atendimento=1800, jornada=28800):
    total_dist = 0
    total_tempo = 0
    tabela_de_para = []
    rota_coords = []
    for i in range(len(coords)-1):
        dist, tempo, path = calcular_segmento(coords[i], coords[i+1])
        total_dist += dist
        total_tempo += tempo
        rota_coords.extend(path)
        tabela_de_para.append({
            "De": f"Cliente {i}" if i>0 else "Origem",
            "Para": f"Cliente {i+1}",
            "Distância (km)": round(dist,2),
            "Tempo (min)": round(tempo/60,2)
        })
    total_tempo += len(coords) * tempo_atendimento
    capacidade = {
        "Clientes atendidos": len(coords),
        "Distância total (km)": round(total_dist,2),
        "Tempo total (HH:MM:SS)": str(timedelta(seconds=int(total_tempo))),
        "Status jornada": "Dentro da jornada" if total_tempo <= jornada else "Fora da jornada"
    }
    return tabela_de_para, capacidade, rota_coords

# Função simples de otimização (permutações - apenas para poucas rotas)
def otimizar_rota(coords):
    melhor_rota = None
    menor_distancia = float("inf")
    for perm in permutations(coords):
        dist_total = 0
        for i in range(len(perm)-1):
            dist, _, _ = calcular_segmento(perm[i], perm[i+1])
            dist_total += dist
        if dist_total < menor_distancia:
            menor_distancia = dist_total
            melhor_rota = perm
    return list(melhor_rota)

# Ler base Excel
df = pd.read_excel("rotas.xlsx")

# Geocodificação (se necessário)
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
st.pydeck_chart(pdk.Deck(
    layers=[pdk.Layer("PathLayer",
                      data=[{"path": rota_coords_orig, "color": [0, 128, 255]}],
                      get_path="path", get_color="color")],
    initial_view_state=pdk.ViewState(latitude=coords_original[0][0],
                                     longitude=coords_original[0][1], zoom=12)
))
st.write("Tabela DE → PARA (Original)")
st.dataframe(pd.DataFrame(tabela_de_para_orig))
st.write("Tabela de Capacidade (Original)")
st.dataframe(pd.DataFrame([capacidade_orig]))

# --- Rota Otimizada ---
coords_otimizada = otimizar_rota(coords_original)
tabela_de_para_otim, capacidade_otim, rota_coords_otim = calcular_rota(coords_otimizada)

st.subheader(f"Rota Otimizada ({motorista} - {veiculo})")
st.pydeck_chart(pdk.Deck(
    layers=[pdk.Layer("PathLayer",
                      data=[{"path": rota_coords_otim, "color": [255, 0, 0]}],
                      get_path="path", get_color="color")],
    initial_view_state=pdk.ViewState(latitude=coords_otimizada[0][0],
                                     longitude=coords_otimizada[0][1], zoom=12)
))
st.write("Tabela DE → PARA (Otimizada)")
st.dataframe(pd.DataFrame(tabela_de_para_otim))
st.write("Tabela de Capacidade (Otimizada)")
st.dataframe(pd.DataFrame([capacidade_otim]))


# In[ ]:




