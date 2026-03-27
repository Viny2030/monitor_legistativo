"""
api_diputados.py
API FastAPI — Monitor Legislativo · Cámara de Diputados
Endpoints: /diputados/*

Uso:
    uvicorn api_diputados:app --reload --port 5001
"""

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
import csv, os, datetime, logging
from typing import Optional

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

app = FastAPI(
    title="Monitor Legislativo — Diputados",
    description="API de composición de la Honorable Cámara de Diputados de la Nación Argentina",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["*"],
)

CSV_LOCAL_PATH = os.path.join(os.path.dirname(__file__), "nomina_diputados.csv")

# ──────────────────────────────────────────────
# DATOS FALLBACK — 257 diputados reales
# Fuente: diputados.gov.ar — Marzo 2026
# ──────────────────────────────────────────────
FALLBACK_DIPUTADOS = [
    {"nombre":"Agüero, Guillermo César","distrito":"CHACO","bloque":"UCR - UNIÓN CÍVICA RADICAL","mandato":"2025-2029","inicio":"10/12/2025"},
    {"nombre":"Aguirre, Hilda","distrito":"LA RIOJA","bloque":"UNIÓN POR LA PATRIA","mandato":"2023-2027","inicio":"10/12/2023"},
    {"nombre":"Ajmechet, Sabrina","distrito":"CIUDAD DE BUENOS AIRES","bloque":"LA LIBERTAD AVANZA","mandato":"2025-2029","inicio":"10/12/2025"},
    {"nombre":"Alí, Ernesto \"Pipi\"","distrito":"SAN LUIS","bloque":"UNIÓN POR LA PATRIA","mandato":"2023-2027","inicio":"31/01/2024"},
    {"nombre":"Almena, Carlos Alberto","distrito":"SAN LUIS","bloque":"LA LIBERTAD AVANZA","mandato":"2025-2029","inicio":"10/12/2025"},
    {"nombre":"Almirón, Lisandro","distrito":"CORRIENTES","bloque":"LA LIBERTAD AVANZA","mandato":"2023-2027","inicio":"10/12/2023"},
    {"nombre":"Álvarez, Claudio","distrito":"SAN LUIS","bloque":"INNOVACIÓN FEDERAL","mandato":"2023-2027","inicio":"10/12/2025"},
    {"nombre":"Andino, Cristian","distrito":"SAN JUAN","bloque":"UNIÓN POR LA PATRIA","mandato":"2025-2029","inicio":"10/12/2025"},
    {"nombre":"Andrade, Javier","distrito":"CIUDAD DE BUENOS AIRES","bloque":"UNIÓN POR LA PATRIA","mandato":"2023-2027","inicio":"10/12/2025"},
    {"nombre":"Andreussi, Barbara","distrito":"JUJUY","bloque":"LA LIBERTAD AVANZA","mandato":"2025-2029","inicio":"10/12/2025"},
    {"nombre":"Ansaloni, Pablo","distrito":"BUENOS AIRES","bloque":"LA LIBERTAD AVANZA","mandato":"2023-2027","inicio":"10/12/2023"},
    {"nombre":"Arabia, Damián","distrito":"CIUDAD DE BUENOS AIRES","bloque":"LA LIBERTAD AVANZA","mandato":"2023-2027","inicio":"10/12/2023"},
    {"nombre":"Araujo Hernández, Jorge Neri","distrito":"TIERRA DEL FUEGO","bloque":"UNIÓN POR LA PATRIA","mandato":"2023-2027","inicio":"10/12/2023"},
    {"nombre":"Ardohain, Martín","distrito":"LA PAMPA","bloque":"PRO","mandato":"2023-2027","inicio":"10/12/2023"},
    {"nombre":"Arrieta, Lourdes Micaela","distrito":"MENDOZA","bloque":"PROVINCIAS UNIDAS","mandato":"2023-2027","inicio":"10/12/2023"},
    {"nombre":"Arrúa, Alberto","distrito":"MISIONES","bloque":"INNOVACIÓN FEDERAL","mandato":"2023-2027","inicio":"10/12/2023"},
    {"nombre":"Aveiro, Martín","distrito":"MENDOZA","bloque":"UNIÓN POR LA PATRIA","mandato":"2023-2027","inicio":"10/12/2023"},
    {"nombre":"Avico, Belén","distrito":"CORDOBA","bloque":"LA LIBERTAD AVANZA","mandato":"2023-2027","inicio":"10/12/2023"},
    {"nombre":"Avila, Fernanda","distrito":"CATAMARCA","bloque":"ELIJO CATAMARCA","mandato":"2023-2027","inicio":"10/12/2023"},
    {"nombre":"Avila, Jorge Antonio","distrito":"CHUBUT","bloque":"PROVINCIAS UNIDAS","mandato":"2023-2027","inicio":"10/12/2023"},
    {"nombre":"Banfi, Karina","distrito":"BUENOS AIRES","bloque":"ADELANTE BUENOS AIRES","mandato":"2023-2027","inicio":"10/12/2023"},
    {"nombre":"Barbur, Marcelo","distrito":"SANTIAGO DEL ESTERO","bloque":"UNIÓN POR LA PATRIA","mandato":"2025-2029","inicio":"10/12/2025"},
    {"nombre":"Basterra, Luis Eugenio","distrito":"FORMOSA","bloque":"UNIÓN POR LA PATRIA","mandato":"2023-2027","inicio":"10/12/2023"},
    {"nombre":"Basualdo, Atilio","distrito":"FORMOSA","bloque":"LA LIBERTAD AVANZA","mandato":"2025-2029","inicio":"17/12/2025"},
    {"nombre":"Basualdo, Carolina","distrito":"CORDOBA","bloque":"PROVINCIAS UNIDAS","mandato":"2025-2029","inicio":"10/12/2025"},
    {"nombre":"Becerra, Mónica","distrito":"SAN LUIS","bloque":"LA LIBERTAD AVANZA","mandato":"2025-2029","inicio":"10/12/2025"},
    {"nombre":"Benedit, Beltrán","distrito":"ENTRE RIOS","bloque":"LA LIBERTAD AVANZA","mandato":"2023-2027","inicio":"10/12/2023"},
    {"nombre":"Benegas Lynch, Bertie","distrito":"BUENOS AIRES","bloque":"LA LIBERTAD AVANZA","mandato":"2023-2027","inicio":"10/12/2023"},
    {"nombre":"Bianchetti, Emmanuel","distrito":"MISIONES","bloque":"PRO","mandato":"2023-2027","inicio":"10/12/2023"},
    {"nombre":"Biella, Bernardo","distrito":"SALTA","bloque":"INNOVACIÓN FEDERAL","mandato":"2025-2029","inicio":"10/12/2025"},
    {"nombre":"Bonacci, Rocío","distrito":"SANTA FE","bloque":"LA LIBERTAD AVANZA","mandato":"2023-2027","inicio":"10/12/2023"},
    {"nombre":"Bongiovanni, Alejandro","distrito":"SANTA FE","bloque":"LA LIBERTAD AVANZA","mandato":"2023-2027","inicio":"10/12/2023"},
    {"nombre":"Bordet, Gustavo","distrito":"ENTRE RIOS","bloque":"UNIÓN POR LA PATRIA","mandato":"2023-2027","inicio":"10/12/2023"},
    {"nombre":"Borgatta, Alejandrina","distrito":"SANTA FE","bloque":"UNIÓN POR LA PATRIA","mandato":"2025-2029","inicio":"10/12/2025"},
    {"nombre":"Bornoroni, Gabriel","distrito":"CORDOBA","bloque":"LA LIBERTAD AVANZA","mandato":"2023-2027","inicio":"10/12/2023"},
    {"nombre":"Bregman, Myriam","distrito":"CIUDAD DE BUENOS AIRES","bloque":"FRENTE DE IZQUIERDA Y DE TRABAJADORES UNIDAD","mandato":"2025-2029","inicio":"10/12/2025"},
    {"nombre":"Brizuela, Adrián","distrito":"CATAMARCA","bloque":"LA LIBERTAD AVANZA","mandato":"2025-2029","inicio":"10/12/2025"},
    {"nombre":"Brügge, Juan Fernando","distrito":"CORDOBA","bloque":"PROVINCIAS UNIDAS","mandato":"2023-2027","inicio":"10/12/2023"},
    {"nombre":"Bruno, Eliana","distrito":"SALTA","bloque":"LA LIBERTAD AVANZA","mandato":"2023-2027","inicio":"10/12/2025"},
    {"nombre":"Cafiero, Santiago","distrito":"BUENOS AIRES","bloque":"UNIÓN POR LA PATRIA","mandato":"2023-2027","inicio":"10/12/2023"},
    {"nombre":"Campero, Mariano","distrito":"TUCUMAN","bloque":"LA LIBERTAD AVANZA","mandato":"2023-2027","inicio":"10/12/2023"},
    {"nombre":"Campitelli, Celia","distrito":"SANTIAGO DEL ESTERO","bloque":"UNIÓN POR LA PATRIA","mandato":"2023-2027","inicio":"10/12/2023"},
    {"nombre":"Campo, Julieta Marisol","distrito":"CHACO","bloque":"UNIÓN POR LA PATRIA","mandato":"2025-2029","inicio":"10/12/2025"},
    {"nombre":"Cámpora, Lucía","distrito":"CIUDAD DE BUENOS AIRES","bloque":"UNIÓN POR LA PATRIA","mandato":"2025-2029","inicio":"10/12/2025"},
    {"nombre":"Capozzi, Sergio Eduardo","distrito":"RIO NEGRO","bloque":"PROVINCIAS UNIDAS","mandato":"2023-2027","inicio":"10/12/2023"},
    {"nombre":"Carignano, Florencia","distrito":"SANTA FE","bloque":"UNIÓN POR LA PATRIA","mandato":"2023-2027","inicio":"10/12/2023"},
    {"nombre":"Carrancio, Alejandro","distrito":"BUENOS AIRES","bloque":"LA LIBERTAD AVANZA","mandato":"2025-2029","inicio":"10/12/2025"},
    {"nombre":"Casas, Sergio Guillermo","distrito":"LA RIOJA","bloque":"UNIÓN POR LA PATRIA","mandato":"2023-2027","inicio":"10/12/2023"},
    {"nombre":"Castagneto, Carlos Daniel","distrito":"BUENOS AIRES","bloque":"UNIÓN POR LA PATRIA","mandato":"2023-2027","inicio":"10/12/2023"},
    {"nombre":"Castelnuovo, Giselle","distrito":"BUENOS AIRES","bloque":"LA LIBERTAD AVANZA","mandato":"2025-2029","inicio":"10/12/2025"},
    {"nombre":"Chica, Jorge","distrito":"SAN JUAN","bloque":"UNIÓN POR LA PATRIA","mandato":"2023-2027","inicio":"10/12/2023"},
    {"nombre":"Chiconi, Abel","distrito":"SAN JUAN","bloque":"LA LIBERTAD AVANZA","mandato":"2025-2029","inicio":"10/12/2025"},
    {"nombre":"Cipolini, Gerardo","distrito":"CHACO","bloque":"UCR - UNIÓN CÍVICA RADICAL","mandato":"2023-2027","inicio":"10/12/2023"},
    {"nombre":"Cisneros, Carlos","distrito":"TUCUMAN","bloque":"UNIÓN POR LA PATRIA","mandato":"2023-2027","inicio":"10/12/2023"},
    {"nombre":"Coletta, Mariela","distrito":"CIUDAD DE BUENOS AIRES","bloque":"PROVINCIAS UNIDAS","mandato":"2023-2027","inicio":"10/12/2023"},
    {"nombre":"Correa Llano, Facundo","distrito":"MENDOZA","bloque":"LA LIBERTAD AVANZA","mandato":"2023-2027","inicio":"10/12/2023"},
    {"nombre":"Daives, Ricardo","distrito":"SANTIAGO DEL ESTERO","bloque":"UNIÓN POR LA PATRIA","mandato":"2023-2027","inicio":"10/12/2023"},
    {"nombre":"de Andreis, Fernando","distrito":"CIUDAD DE BUENOS AIRES","bloque":"PRO","mandato":"2025-2029","inicio":"10/12/2025"},
    {"nombre":"de la Rosa, María Graciela","distrito":"FORMOSA","bloque":"UNIÓN POR LA PATRIA","mandato":"2025-2029","inicio":"10/12/2025"},
    {"nombre":"de la Sota, Natalia","distrito":"CORDOBA","bloque":"DEFENDAMOS CÓRDOBA","mandato":"2025-2029","inicio":"10/12/2025"},
    {"nombre":"De Sensi, María Florencia","distrito":"BUENOS AIRES","bloque":"PRO","mandato":"2025-2029","inicio":"10/12/2025"},
    {"nombre":"del Caño, Nicolás","distrito":"BUENOS AIRES","bloque":"FRENTE DE IZQUIERDA Y DE TRABAJADORES UNIDAD","mandato":"2025-2029","inicio":"10/12/2025"},
    {"nombre":"Del Plá, Romina","distrito":"BUENOS AIRES","bloque":"FRENTE DE IZQUIERDA Y DE TRABAJADORES UNIDAD","mandato":"2025-2029","inicio":"10/12/2025"},
    {"nombre":"Díaz, Fernanda","distrito":"BUENOS AIRES","bloque":"UNIÓN POR LA PATRIA","mandato":"2025-2029","inicio":"10/12/2025"},
    {"nombre":"Diez, Romina","distrito":"SANTA FE","bloque":"LA LIBERTAD AVANZA","mandato":"2023-2027","inicio":"10/12/2023"},
    {"nombre":"Dolce, Sergio","distrito":"CHACO","bloque":"UNIÓN POR LA PATRIA","mandato":"2025-2029","inicio":"10/12/2025"},
    {"nombre":"Emma, Nicolás","distrito":"CIUDAD DE BUENOS AIRES","bloque":"LA LIBERTAD AVANZA","mandato":"2025-2029","inicio":"10/12/2025"},
    {"nombre":"Estévez, Gabriela Beatriz","distrito":"CORDOBA","bloque":"UNIÓN POR LA PATRIA","mandato":"2023-2027","inicio":"10/12/2023"},
    {"nombre":"Falcone, Eduardo","distrito":"BUENOS AIRES","bloque":"MID - MOVIMIENTO DE INTEGRACIÓN Y DESARROLLO","mandato":"2023-2027","inicio":"10/12/2023"},
    {"nombre":"Fargosi, Alejandro","distrito":"CIUDAD DE BUENOS AIRES","bloque":"LA LIBERTAD AVANZA","mandato":"2025-2029","inicio":"10/12/2025"},
    {"nombre":"Farías, Pablo","distrito":"SANTA FE","bloque":"PROVINCIAS UNIDAS","mandato":"2025-2029","inicio":"10/12/2025"},
    {"nombre":"Félix, Emir","distrito":"MENDOZA","bloque":"UNIÓN POR LA PATRIA","mandato":"2025-2029","inicio":"10/12/2025"},
    {"nombre":"Fernández, Jorge","distrito":"SAN LUIS","bloque":"PRIMERO SAN LUIS","mandato":"2025-2029","inicio":"10/12/2025"},
    {"nombre":"Fernández, Elia Marina","distrito":"TUCUMAN","bloque":"INDEPENDENCIA","mandato":"2023-2027","inicio":"10/12/2025"},
    {"nombre":"Fernández Molero, Daiana","distrito":"CIUDAD DE BUENOS AIRES","bloque":"PRO","mandato":"2023-2027","inicio":"10/12/2023"},
    {"nombre":"Ferrán, Abelardo","distrito":"LA PAMPA","bloque":"UNIÓN POR LA PATRIA","mandato":"2025-2029","inicio":"10/12/2025"},
    {"nombre":"Ferraro, Maximiliano","distrito":"CIUDAD DE BUENOS AIRES","bloque":"COALICION CIVICA","mandato":"2023-2027","inicio":"10/12/2023"},
    {"nombre":"Ferreyra, Alida","distrito":"CIUDAD DE BUENOS AIRES","bloque":"LA LIBERTAD AVANZA","mandato":"2023-2027","inicio":"31/01/2024"},
    {"nombre":"Figliuolo, Sergio","distrito":"BUENOS AIRES","bloque":"LA LIBERTAD AVANZA","mandato":"2025-2029","inicio":"10/12/2025"},
    {"nombre":"Finocchiaro, Alejandro","distrito":"BUENOS AIRES","bloque":"PRO","mandato":"2025-2029","inicio":"10/12/2025"},
    {"nombre":"Flores, Maria Gabriela","distrito":"SALTA","bloque":"LA LIBERTAD AVANZA","mandato":"2025-2029","inicio":"10/12/2025"},
    {"nombre":"Frade, Mónica","distrito":"BUENOS AIRES","bloque":"COALICION CIVICA","mandato":"2023-2027","inicio":"10/12/2023"},
    {"nombre":"Fregonese, Alicia","distrito":"ENTRE RIOS","bloque":"PRO","mandato":"2025-2029","inicio":"10/12/2025"},
    {"nombre":"Freites, Andrea","distrito":"TIERRA DEL FUEGO","bloque":"UNIÓN POR LA PATRIA","mandato":"2023-2027","inicio":"10/12/2023"},
    {"nombre":"Frias, Maira","distrito":"CHUBUT","bloque":"LA LIBERTAD AVANZA","mandato":"2025-2029","inicio":"10/12/2025"},
    {"nombre":"Gallardo, María Virginia","distrito":"CORRIENTES","bloque":"LA LIBERTAD AVANZA","mandato":"2025-2029","inicio":"10/12/2025"},
    {"nombre":"Galmarini, Sebastián","distrito":"BUENOS AIRES","bloque":"UNIÓN POR LA PATRIA","mandato":"2025-2029","inicio":"10/12/2025"},
    {"nombre":"García, Álvaro","distrito":"BUENOS AIRES","bloque":"LA LIBERTAD AVANZA","mandato":"2025-2029","inicio":"10/12/2025"},
    {"nombre":"García, María Teresa","distrito":"BUENOS AIRES","bloque":"UNIÓN POR LA PATRIA","mandato":"2025-2029","inicio":"10/12/2025"},
    {"nombre":"García, Carlos","distrito":"CHACO","bloque":"LA LIBERTAD AVANZA","mandato":"2023-2027","inicio":"10/12/2023"},
    {"nombre":"García Aresca, Ignacio","distrito":"CORDOBA","bloque":"PROVINCIAS UNIDAS","mandato":"2025-2029","inicio":"10/12/2025"},
    {"nombre":"Garrido, José Luis","distrito":"SANTA CRUZ","bloque":"POR SANTA CRUZ","mandato":"2023-2027","inicio":"10/12/2023"},
    {"nombre":"Giampieri, Antonela","distrito":"CIUDAD DE BUENOS AIRES","bloque":"PRO","mandato":"2025-2029","inicio":"10/12/2025"},
    {"nombre":"Giudici, Silvana","distrito":"CIUDAD DE BUENOS AIRES","bloque":"LA LIBERTAD AVANZA","mandato":"2023-2027","inicio":"10/12/2023"},
    {"nombre":"Giuliano, Diego A.","distrito":"SANTA FE","bloque":"UNIÓN POR LA PATRIA","mandato":"2023-2027","inicio":"10/12/2023"},
    {"nombre":"Glinski, José","distrito":"CHUBUT","bloque":"UNIÓN POR LA PATRIA","mandato":"2023-2027","inicio":"10/12/2023"},
    {"nombre":"Goitia, Rosario","distrito":"CHACO","bloque":"LA LIBERTAD AVANZA","mandato":"2025-2029","inicio":"10/12/2025"},
    {"nombre":"Gomez, José","distrito":"SANTIAGO DEL ESTERO","bloque":"UNIÓN POR LA PATRIA","mandato":"2023-2027","inicio":"10/12/2023"},
    {"nombre":"Gonzales, Alfredo","distrito":"JUJUY","bloque":"LA LIBERTAD AVANZA","mandato":"2025-2029","inicio":"10/12/2025"},
    {"nombre":"González, Diógenes Ignacio","distrito":"CORRIENTES","bloque":"UCR - UNIÓN CÍVICA RADICAL","mandato":"2025-2029","inicio":"10/12/2025"},
    {"nombre":"González, Álvaro","distrito":"CIUDAD DE BUENOS AIRES","bloque":"PRO","mandato":"2023-2027","inicio":"10/12/2023"},
    {"nombre":"González, Gerardo Gustavo","distrito":"FORMOSA","bloque":"INNOVACIÓN FEDERAL","mandato":"2023-2027","inicio":"10/12/2023"},
    {"nombre":"González Estevarena, María Luisa","distrito":"BUENOS AIRES","bloque":"LA LIBERTAD AVANZA","mandato":"2025-2029","inicio":"10/12/2025"},
    {"nombre":"Grabois, Juan","distrito":"BUENOS AIRES","bloque":"UNIÓN POR LA PATRIA","mandato":"2025-2029","inicio":"10/12/2025"},
    {"nombre":"Gruber, Maura","distrito":"MISIONES","bloque":"LA LIBERTAD AVANZA","mandato":"2025-2029","inicio":"10/12/2025"},
    {"nombre":"Gutiérrez, Ramiro","distrito":"BUENOS AIRES","bloque":"UNIÓN POR LA PATRIA","mandato":"2023-2027","inicio":"10/12/2023"},
    {"nombre":"Gutiérrez, Carlos","distrito":"CORDOBA","bloque":"PROVINCIAS UNIDAS","mandato":"2023-2027","inicio":"10/12/2023"},
    {"nombre":"Guzmán, Jairo","distrito":"SANTA CRUZ","bloque":"LA LIBERTAD AVANZA","mandato":"2025-2029","inicio":"10/12/2025"},
    {"nombre":"Hadad, Raúl","distrito":"CORRIENTES","bloque":"UNIÓN POR LA PATRIA","mandato":"2025-2029","inicio":"10/12/2025"},
    {"nombre":"Hagman, Itai","distrito":"CIUDAD DE BUENOS AIRES","bloque":"UNIÓN POR LA PATRIA","mandato":"2025-2029","inicio":"10/12/2025"},
    {"nombre":"Hartfield, Diego","distrito":"MISIONES","bloque":"LA LIBERTAD AVANZA","mandato":"2025-2029","inicio":"10/12/2025"},
    {"nombre":"Herrera, Oscar","distrito":"MISIONES","bloque":"INNOVACIÓN FEDERAL","mandato":"2025-2029","inicio":"10/12/2025"},
    {"nombre":"Holzman, Patricia","distrito":"CIUDAD DE BUENOS AIRES","bloque":"LA LIBERTAD AVANZA","mandato":"2025-2029","inicio":"10/12/2025"},
    {"nombre":"Huesen, Gerardo","distrito":"TUCUMAN","bloque":"LA LIBERTAD AVANZA","mandato":"2023-2027","inicio":"10/12/2023"},
    {"nombre":"Humenuk, Gladys","distrito":"BUENOS AIRES","bloque":"LA LIBERTAD AVANZA","mandato":"2025-2029","inicio":"10/12/2025"},
    {"nombre":"Ianni, Ana María","distrito":"SANTA CRUZ","bloque":"UNIÓN POR LA PATRIA","mandato":"2023-2027","inicio":"10/12/2023"},
    {"nombre":"Ibañez, María Cecilia","distrito":"CORDOBA","bloque":"LA LIBERTAD AVANZA","mandato":"2023-2027","inicio":"10/12/2023"},
    {"nombre":"Jaime Quiroga, Carlos Gustavo","distrito":"SAN JUAN","bloque":"PRODUCCION Y TRABAJO","mandato":"2025-2029","inicio":"10/12/2025"},
    {"nombre":"Juliano, Pablo","distrito":"BUENOS AIRES","bloque":"PROVINCIAS UNIDAS","mandato":"2023-2027","inicio":"10/12/2023"},
    {"nombre":"Kirchner, Máximo Carlos","distrito":"BUENOS AIRES","bloque":"UNIÓN POR LA PATRIA","mandato":"2023-2027","inicio":"10/12/2023"},
    {"nombre":"Lanesan Sancho, Moira","distrito":"SANTA CRUZ","bloque":"UNIÓN POR LA PATRIA","mandato":"2025-2029","inicio":"10/12/2025"},
    {"nombre":"Laumann, Andrés Ariel","distrito":"ENTRE RIOS","bloque":"LA LIBERTAD AVANZA","mandato":"2025-2029","inicio":"10/12/2025"},
    {"nombre":"Leiva, Aldo","distrito":"CHACO","bloque":"UNIÓN POR LA PATRIA","mandato":"2023-2027","inicio":"10/12/2023"},
    {"nombre":"Lemoine, Lilia","distrito":"BUENOS AIRES","bloque":"LA LIBERTAD AVANZA","mandato":"2023-2027","inicio":"10/12/2023"},
    {"nombre":"Leone, Andrés","distrito":"CIUDAD DE BUENOS AIRES","bloque":"LA LIBERTAD AVANZA","mandato":"2025-2029","inicio":"10/12/2025"},
    {"nombre":"Llano, Mercedes","distrito":"MENDOZA","bloque":"LA LIBERTAD AVANZA","mandato":"2023-2027","inicio":"10/12/2023"},
    {"nombre":"Lluch, Enrique","distrito":"CORDOBA","bloque":"LA LIBERTAD AVANZA","mandato":"2025-2029","inicio":"10/12/2025"},
    {"nombre":"Longo, Johanna Sabrina","distrito":"BUENOS AIRES","bloque":"LA LIBERTAD AVANZA","mandato":"2025-2029","inicio":"10/12/2025"},
    {"nombre":"López, Jimena","distrito":"BUENOS AIRES","bloque":"UNIÓN POR LA PATRIA","mandato":"2025-2029","inicio":"10/12/2025"},
    {"nombre":"López Pasquali, Cecilia","distrito":"SANTIAGO DEL ESTERO","bloque":"UNIÓN POR LA PATRIA","mandato":"2025-2029","inicio":"10/12/2025"},
    {"nombre":"Lousteau, Martín","distrito":"CIUDAD DE BUENOS AIRES","bloque":"PROVINCIAS UNIDAS","mandato":"2025-2029","inicio":"10/12/2025"},
    {"nombre":"Luque, Juan Pablo","distrito":"CHUBUT","bloque":"UNIÓN POR LA PATRIA","mandato":"2025-2029","inicio":"10/12/2025"},
    {"nombre":"Macyszyn, Lorena","distrito":"BUENOS AIRES","bloque":"LA LIBERTAD AVANZA","mandato":"2023-2027","inicio":"10/12/2023"},
    {"nombre":"Mango, Marcelo","distrito":"RIO NEGRO","bloque":"UNIÓN POR LA PATRIA","mandato":"2023-2027","inicio":"10/12/2025"},
    {"nombre":"Manrique, Mario","distrito":"BUENOS AIRES","bloque":"UNIÓN POR LA PATRIA","mandato":"2023-2027","inicio":"10/12/2023"},
    {"nombre":"Marclay, Marianela","distrito":"ENTRE RIOS","bloque":"UNIÓN POR LA PATRIA","mandato":"2025-2029","inicio":"10/12/2025"},
    {"nombre":"Marín, Varinia Lis","distrito":"LA PAMPA","bloque":"UNIÓN POR LA PATRIA","mandato":"2025-2029","inicio":"10/12/2025"},
    {"nombre":"Marino, Juan","distrito":"BUENOS AIRES","bloque":"UNIÓN POR LA PATRIA","mandato":"2023-2027","inicio":"10/12/2023"},
    {"nombre":"Martínez, Álvaro","distrito":"MENDOZA","bloque":"LA LIBERTAD AVANZA","mandato":"2025-2029","inicio":"10/12/2025"},
    {"nombre":"Martínez, Germán Pedro","distrito":"SANTA FE","bloque":"UNIÓN POR LA PATRIA","mandato":"2023-2027","inicio":"10/12/2023"},
    {"nombre":"Massot, Nicolás","distrito":"BUENOS AIRES","bloque":"ENCUENTRO FEDERAL","mandato":"2023-2027","inicio":"10/12/2023"},
    {"nombre":"Maureira, Karina","distrito":"NEUQUEN","bloque":"LA NEUQUINIDAD","mandato":"2025-2029","inicio":"10/12/2025"},
    {"nombre":"Mayoraz, Nicolás","distrito":"SANTA FE","bloque":"LA LIBERTAD AVANZA","mandato":"2023-2027","inicio":"10/12/2023"},
    {"nombre":"Medina, Gladys","distrito":"TUCUMAN","bloque":"INDEPENDENCIA","mandato":"2025-2029","inicio":"10/12/2025"},
    {"nombre":"Menem, Martín","distrito":"LA RIOJA","bloque":"LA LIBERTAD AVANZA","mandato":"2023-2027","inicio":"10/12/2023"},
    {"nombre":"Metral Asensio, Julieta","distrito":"MENDOZA","bloque":"LA LIBERTAD AVANZA","mandato":"2025-2029","inicio":"10/12/2025"},
    {"nombre":"Michel, Guillermo","distrito":"ENTRE RIOS","bloque":"UNIÓN POR LA PATRIA","mandato":"2025-2029","inicio":"10/12/2025"},
    {"nombre":"Miño, Fernanda","distrito":"BUENOS AIRES","bloque":"UNIÓN POR LA PATRIA","mandato":"2025-2029","inicio":"10/12/2025"},
    {"nombre":"Molina, Juan Carlos","distrito":"SANTA CRUZ","bloque":"UNIÓN POR LA PATRIA","mandato":"2025-2029","inicio":"10/12/2025"},
    {"nombre":"Molinuevo, Soledad","distrito":"TUCUMAN","bloque":"LA LIBERTAD AVANZA","mandato":"2025-2029","inicio":"10/12/2025"},
    {"nombre":"Molle, Matías","distrito":"BUENOS AIRES","bloque":"UNIÓN POR LA PATRIA","mandato":"2023-2027","inicio":"10/12/2023"},
    {"nombre":"Mondaca, Soledad","distrito":"NEUQUEN","bloque":"LA LIBERTAD AVANZA","mandato":"2025-2029","inicio":"10/12/2025"},
    {"nombre":"Monguillot, Fernando","distrito":"CATAMARCA","bloque":"ELIJO CATAMARCA","mandato":"2025-2029","inicio":"10/12/2025"},
    {"nombre":"Montenegro, Juan Pablo","distrito":"SANTA FE","bloque":"LA LIBERTAD AVANZA","mandato":"2025-2029","inicio":"10/12/2025"},
    {"nombre":"Montenegro, Guillermo","distrito":"BUENOS AIRES","bloque":"LA LIBERTAD AVANZA","mandato":"2023-2027","inicio":"10/12/2023"},
    {"nombre":"Monzón, Roxana","distrito":"BUENOS AIRES","bloque":"UNIÓN POR LA PATRIA","mandato":"2023-2027","inicio":"10/12/2023"},
    {"nombre":"Morchio, Francisco","distrito":"ENTRE RIOS","bloque":"LA LIBERTAD AVANZA","mandato":"2023-2027","inicio":"10/12/2023"},
    {"nombre":"Moreau, Cecilia","distrito":"BUENOS AIRES","bloque":"UNIÓN POR LA PATRIA","mandato":"2023-2027","inicio":"10/12/2023"},
    {"nombre":"Moreno Ovalle, Julio","distrito":"SALTA","bloque":"LA LIBERTAD AVANZA","mandato":"2023-2027","inicio":"10/12/2023"},
    {"nombre":"Moyano, Hugo Antonio","distrito":"BUENOS AIRES","bloque":"UNIÓN POR LA PATRIA","mandato":"2025-2029","inicio":"10/12/2025"},
    {"nombre":"Mukdise, Jorge","distrito":"SANTIAGO DEL ESTERO","bloque":"UNIÓN POR LA PATRIA","mandato":"2025-2029","inicio":"10/12/2025"},
    {"nombre":"Muñoz, Gabriela Luciana","distrito":"NEUQUEN","bloque":"LA LIBERTAD AVANZA","mandato":"2023-2027","inicio":"10/12/2025"},
    {"nombre":"Neder, Estela Mary","distrito":"SANTIAGO DEL ESTERO","bloque":"UNIÓN POR LA PATRIA","mandato":"2023-2027","inicio":"10/12/2023"},
    {"nombre":"Nieri, Lisandro","distrito":"MENDOZA","bloque":"UCR - UNIÓN CÍVICA RADICAL","mandato":"2023-2027","inicio":"10/12/2023"},
    {"nombre":"Niveyro, Miriam","distrito":"BUENOS AIRES","bloque":"LA LIBERTAD AVANZA","mandato":"2025-2029","inicio":"10/12/2025"},
    {"nombre":"Nóblega, Sebastián","distrito":"CATAMARCA","bloque":"ELIJO CATAMARCA","mandato":"2023-2027","inicio":"10/12/2023"},
    {"nombre":"Noguera, Javier","distrito":"TUCUMAN","bloque":"INDEPENDENCIA","mandato":"2025-2029","inicio":"10/12/2025"},
    {"nombre":"Nuñez, José","distrito":"SANTA FE","bloque":"PROVINCIAS UNIDAS","mandato":"2023-2027","inicio":"10/12/2023"},
    {"nombre":"Ojeda, Joaquín","distrito":"BUENOS AIRES","bloque":"LA LIBERTAD AVANZA","mandato":"2025-2029","inicio":"10/12/2025"},
    {"nombre":"Olmos, Kelly","distrito":"CIUDAD DE BUENOS AIRES","bloque":"UNIÓN POR LA PATRIA","mandato":"2025-2029","inicio":"10/12/2025"},
    {"nombre":"Osuna, Blanca Inés","distrito":"ENTRE RIOS","bloque":"UNIÓN POR LA PATRIA","mandato":"2023-2027","inicio":"10/12/2023"},
    {"nombre":"Outes, Pablo","distrito":"SALTA","bloque":"INNOVACIÓN FEDERAL","mandato":"2023-2027","inicio":"10/12/2023"},
    {"nombre":"Pagano, Marcela Marina","distrito":"BUENOS AIRES","bloque":"COHERENCIA","mandato":"2023-2027","inicio":"10/12/2023"},
    {"nombre":"Palazzo, Sergio Omar","distrito":"BUENOS AIRES","bloque":"UNIÓN POR LA PATRIA","mandato":"2025-2029","inicio":"10/12/2025"},
    {"nombre":"Palladino, Claudia María","distrito":"CATAMARCA","bloque":"UNIÓN POR LA PATRIA","mandato":"2025-2029","inicio":"10/12/2025"},
    {"nombre":"Pareja, Sebastián","distrito":"BUENOS AIRES","bloque":"LA LIBERTAD AVANZA","mandato":"2025-2029","inicio":"10/12/2025"},
    {"nombre":"Parola, María Graciela","distrito":"FORMOSA","bloque":"UNIÓN POR LA PATRIA","mandato":"2023-2027","inicio":"10/12/2023"},
    {"nombre":"Patiño Brizuela, Marcos","distrito":"CORDOBA","bloque":"LA LIBERTAD AVANZA","mandato":"2025-2029","inicio":"10/12/2025"},
    {"nombre":"Pauli, Santiago","distrito":"TIERRA DEL FUEGO","bloque":"LA LIBERTAD AVANZA","mandato":"2023-2027","inicio":"10/12/2023"},
    {"nombre":"Paulón, Esteban","distrito":"SANTA FE","bloque":"PROVINCIAS UNIDAS","mandato":"2023-2027","inicio":"10/12/2023"},
    {"nombre":"Pedrali, Gabriela","distrito":"LA RIOJA","bloque":"UNIÓN POR LA PATRIA","mandato":"2025-2029","inicio":"10/12/2025"},
    {"nombre":"Pellegrini, Agustín","distrito":"SANTA FE","bloque":"LA LIBERTAD AVANZA","mandato":"2025-2029","inicio":"10/12/2025"},
    {"nombre":"Pelli, Federico Agustín","distrito":"TUCUMAN","bloque":"LA LIBERTAD AVANZA","mandato":"2025-2029","inicio":"10/12/2025"},
    {"nombre":"Peluc, José","distrito":"SAN JUAN","bloque":"LA LIBERTAD AVANZA","mandato":"2023-2027","inicio":"10/12/2023"},
    {"nombre":"Penacca, Paula Andrea","distrito":"CIUDAD DE BUENOS AIRES","bloque":"UNIÓN POR LA PATRIA","mandato":"2023-2027","inicio":"10/12/2023"},
    {"nombre":"Petri, Luis","distrito":"MENDOZA","bloque":"LA LIBERTAD AVANZA","mandato":"2025-2029","inicio":"10/12/2025"},
    {"nombre":"Petrovich, María Lorena","distrito":"BUENOS AIRES","bloque":"LA LIBERTAD AVANZA","mandato":"2023-2027","inicio":"10/12/2025"},
    {"nombre":"Picat, Luis Albino","distrito":"CORDOBA","bloque":"LA LIBERTAD AVANZA","mandato":"2023-2027","inicio":"10/12/2023"},
    {"nombre":"Pichetto, Miguel Ángel","distrito":"BUENOS AIRES","bloque":"ENCUENTRO FEDERAL","mandato":"2023-2027","inicio":"10/12/2023"},
    {"nombre":"Picón Martínez, Nancy Viviana","distrito":"SAN JUAN","bloque":"PRODUCCION Y TRABAJO","mandato":"2023-2027","inicio":"10/12/2023"},
    {"nombre":"Pietragalla Corti, Horacio","distrito":"BUENOS AIRES","bloque":"UNIÓN POR LA PATRIA","mandato":"2025-2029","inicio":"10/12/2025"},
    {"nombre":"Pitrola, Nestor","distrito":"BUENOS AIRES","bloque":"FRENTE DE IZQUIERDA Y DE TRABAJADORES UNIDAD","mandato":"2023-2027","inicio":"10/12/2025"},
    {"nombre":"Pokoik, Lorena","distrito":"CIUDAD DE BUENOS AIRES","bloque":"UNIÓN POR LA PATRIA","mandato":"2023-2027","inicio":"10/12/2023"},
    {"nombre":"Ponce, María Celeste","distrito":"CORDOBA","bloque":"LA LIBERTAD AVANZA","mandato":"2023-2027","inicio":"10/12/2023"},
    {"nombre":"Potenza, Luciana","distrito":"BUENOS AIRES","bloque":"UNIÓN POR LA PATRIA","mandato":"2023-2027","inicio":"10/12/2023"},
    {"nombre":"Propato, Agustina Lucrecia","distrito":"BUENOS AIRES","bloque":"UNIÓN POR LA PATRIA","mandato":"2025-2029","inicio":"10/12/2025"},
    {"nombre":"Quintar, Manuel","distrito":"JUJUY","bloque":"LA LIBERTAD AVANZA","mandato":"2023-2027","inicio":"10/12/2023"},
    {"nombre":"Rauschenberger, Ariel","distrito":"LA PAMPA","bloque":"UNIÓN POR LA PATRIA","mandato":"2023-2027","inicio":"10/12/2023"},
    {"nombre":"Ravera, Valentina","distrito":"SANTA FE","bloque":"LA LIBERTAD AVANZA","mandato":"2025-2029","inicio":"10/12/2025"},
    {"nombre":"Ravier, Adrián","distrito":"LA PAMPA","bloque":"LA LIBERTAD AVANZA","mandato":"2025-2029","inicio":"10/12/2025"},
    {"nombre":"Razzini, Verónica","distrito":"SANTA FE","bloque":"LA LIBERTAD AVANZA","mandato":"2023-2027","inicio":"10/12/2023"},
    {"nombre":"Reichardt, Karen","distrito":"BUENOS AIRES","bloque":"LA LIBERTAD AVANZA","mandato":"2025-2029","inicio":"10/12/2025"},
    {"nombre":"Riesco, Gastón","distrito":"NEUQUEN","bloque":"LA LIBERTAD AVANZA","mandato":"2025-2029","inicio":"10/12/2025"},
    {"nombre":"Ritondo, Cristian A.","distrito":"BUENOS AIRES","bloque":"PRO","mandato":"2023-2027","inicio":"10/12/2023"},
    {"nombre":"Rizzotti, Jorge","distrito":"JUJUY","bloque":"PROVINCIAS UNIDAS","mandato":"2023-2027","inicio":"10/12/2023"},
    {"nombre":"Roberto, Santiago Luis","distrito":"CIUDAD DE BUENOS AIRES","bloque":"UNIÓN POR LA PATRIA","mandato":"2025-2029","inicio":"10/12/2025"},
    {"nombre":"Roca, Gonzalo","distrito":"CORDOBA","bloque":"LA LIBERTAD AVANZA","mandato":"2025-2029","inicio":"10/12/2025"},
    {"nombre":"Rodríguez, Miguel","distrito":"TIERRA DEL FUEGO","bloque":"LA LIBERTAD AVANZA","mandato":"2025-2029","inicio":"10/12/2025"},
    {"nombre":"Rodríguez Machado, Laura Elena","distrito":"CORDOBA","bloque":"LA LIBERTAD AVANZA","mandato":"2025-2029","inicio":"10/12/2025"},
    {"nombre":"Rossi, Agustín Oscar","distrito":"SANTA FE","bloque":"UNIÓN POR LA PATRIA","mandato":"2025-2029","inicio":"10/12/2025"},
    {"nombre":"Ruíz, Yamila","distrito":"MISIONES","bloque":"INNOVACIÓN FEDERAL","mandato":"2023-2027","inicio":"10/12/2023"},
    {"nombre":"Salzmann, Marina Dorotea","distrito":"BUENOS AIRES","bloque":"UNIÓN POR LA PATRIA","mandato":"2025-2029","inicio":"10/12/2025"},
    {"nombre":"Sánchez Wrba, Javier","distrito":"BUENOS AIRES","bloque":"PRO","mandato":"2025-2029","inicio":"10/12/2025"},
    {"nombre":"Sand, Nancy","distrito":"CORRIENTES","bloque":"UNIÓN POR LA PATRIA","mandato":"2023-2027","inicio":"10/12/2023"},
    {"nombre":"Santillán Juárez Brahim, Juliana","distrito":"BUENOS AIRES","bloque":"LA LIBERTAD AVANZA","mandato":"2023-2027","inicio":"10/12/2023"},
    {"nombre":"Santurio, Santiago","distrito":"BUENOS AIRES","bloque":"LA LIBERTAD AVANZA","mandato":"2023-2027","inicio":"10/12/2023"},
    {"nombre":"Scaglia, Gisela","distrito":"SANTA FE","bloque":"PROVINCIAS UNIDAS","mandato":"2025-2029","inicio":"10/12/2025"},
    {"nombre":"Schiaretti, Juan","distrito":"CORDOBA","bloque":"PROVINCIAS UNIDAS","mandato":"2025-2029","inicio":"12/02/2026"},
    {"nombre":"Schneider, Darío","distrito":"ENTRE RIOS","bloque":"UCR - UNIÓN CÍVICA RADICAL","mandato":"2025-2029","inicio":"10/12/2025"},
    {"nombre":"Selva, Sabrina","distrito":"BUENOS AIRES","bloque":"UNIÓN POR LA PATRIA","mandato":"2023-2027","inicio":"10/12/2023"},
    {"nombre":"Serquis, Adriana Cristina","distrito":"RIO NEGRO","bloque":"UNIÓN POR LA PATRIA","mandato":"2025-2029","inicio":"10/12/2025"},
    {"nombre":"Siley, Vanesa Raquel","distrito":"BUENOS AIRES","bloque":"UNIÓN POR LA PATRIA","mandato":"2025-2029","inicio":"10/12/2025"},
    {"nombre":"Snopek, Guillermo","distrito":"JUJUY","bloque":"UNIÓN POR LA PATRIA","mandato":"2023-2027","inicio":"10/12/2023"},
    {"nombre":"Soldano, Laura","distrito":"CORDOBA","bloque":"LA LIBERTAD AVANZA","mandato":"2025-2029","inicio":"10/12/2025"},
    {"nombre":"Strada, Julia","distrito":"BUENOS AIRES","bloque":"UNIÓN POR LA PATRIA","mandato":"2023-2027","inicio":"10/12/2023"},
    {"nombre":"Taiana, Jorge","distrito":"BUENOS AIRES","bloque":"UNIÓN POR LA PATRIA","mandato":"2025-2029","inicio":"10/12/2025"},
    {"nombre":"Tailhade, Rodolfo","distrito":"BUENOS AIRES","bloque":"UNIÓN POR LA PATRIA","mandato":"2023-2027","inicio":"10/12/2023"},
    {"nombre":"Tepp, Caren","distrito":"SANTA FE","bloque":"UNIÓN POR LA PATRIA","mandato":"2025-2029","inicio":"10/12/2025"},
    {"nombre":"Tita, Paulo Agustín","distrito":"TIERRA DEL FUEGO","bloque":"UNIÓN POR LA PATRIA","mandato":"2025-2029","inicio":"10/12/2025"},
    {"nombre":"Todero, Pablo","distrito":"NEUQUEN","bloque":"UNIÓN POR LA PATRIA","mandato":"2023-2027","inicio":"10/12/2023"},
    {"nombre":"Tolosa Paz, Victoria","distrito":"BUENOS AIRES","bloque":"UNIÓN POR LA PATRIA","mandato":"2023-2027","inicio":"10/12/2023"},
    {"nombre":"Tomassoni, Yamile","distrito":"SANTA FE","bloque":"LA LIBERTAD AVANZA","mandato":"2025-2029","inicio":"10/12/2025"},
    {"nombre":"Torres, Rubén Darío","distrito":"BUENOS AIRES","bloque":"LA LIBERTAD AVANZA","mandato":"2025-2029","inicio":"10/12/2025"},
    {"nombre":"Torres, Alejandra","distrito":"CORDOBA","bloque":"PROVINCIAS UNIDAS","mandato":"2023-2027","inicio":"10/12/2023"},
    {"nombre":"Tortoriello, Aníbal","distrito":"RIO NEGRO","bloque":"LA LIBERTAD AVANZA","mandato":"2025-2029","inicio":"10/12/2025"},
    {"nombre":"Tournier, José Federico","distrito":"CORRIENTES","bloque":"LA LIBERTAD AVANZA","mandato":"2023-2027","inicio":"14/08/2024"},
    {"nombre":"Treffinger, César","distrito":"CHUBUT","bloque":"LA LIBERTAD AVANZA","mandato":"2023-2027","inicio":"10/12/2023"},
    {"nombre":"Trotta, Nicolás Alfredo","distrito":"BUENOS AIRES","bloque":"UNIÓN POR LA PATRIA","mandato":"2025-2029","inicio":"10/12/2025"},
    {"nombre":"Urien, Hernán","distrito":"BUENOS AIRES","bloque":"LA LIBERTAD AVANZA","mandato":"2025-2029","inicio":"10/12/2025"},
    {"nombre":"Valdés, Eduardo Félix","distrito":"CIUDAD DE BUENOS AIRES","bloque":"UNIÓN POR LA PATRIA","mandato":"2023-2027","inicio":"10/12/2023"},
    {"nombre":"Vancsik, Daniel","distrito":"MISIONES","bloque":"INNOVACIÓN FEDERAL","mandato":"2023-2027","inicio":"10/12/2023"},
    {"nombre":"Vásquez, Patricia","distrito":"BUENOS AIRES","bloque":"LA LIBERTAD AVANZA","mandato":"2023-2027","inicio":"10/12/2023"},
    {"nombre":"Vega, Yolanda","distrito":"SALTA","bloque":"INNOVACIÓN FEDERAL","mandato":"2023-2027","inicio":"10/12/2023"},
    {"nombre":"Velázquez, M. Elena","distrito":"BUENOS AIRES","bloque":"UNIÓN POR LA PATRIA","mandato":"2025-2029","inicio":"10/12/2025"},
    {"nombre":"Vera, Andrea Fernanda","distrito":"BUENOS AIRES","bloque":"LA LIBERTAD AVANZA","mandato":"2025-2029","inicio":"10/12/2025"},
    {"nombre":"Verasay, Pamela Fernanda","distrito":"MENDOZA","bloque":"UCR - UNIÓN CÍVICA RADICAL","mandato":"2025-2029","inicio":"10/12/2025"},
    {"nombre":"Villaverde, Lorena","distrito":"RIO NEGRO","bloque":"LA LIBERTAD AVANZA","mandato":"2023-2027","inicio":"10/12/2023"},
    {"nombre":"Visconti, Gino","distrito":"LA RIOJA","bloque":"LA LIBERTAD AVANZA","mandato":"2025-2029","inicio":"10/12/2025"},
    {"nombre":"Volnovich, Luana","distrito":"BUENOS AIRES","bloque":"UNIÓN POR LA PATRIA","mandato":"2023-2027","inicio":"10/12/2023"},
    {"nombre":"Yasky, Hugo","distrito":"BUENOS AIRES","bloque":"UNIÓN POR LA PATRIA","mandato":"2025-2029","inicio":"10/12/2025"},
    {"nombre":"Yedlin, Pablo Raúl","distrito":"TUCUMAN","bloque":"UNIÓN POR LA PATRIA","mandato":"2023-2027","inicio":"10/12/2023"},
    {"nombre":"Yeza, Martín","distrito":"BUENOS AIRES","bloque":"PRO","mandato":"2023-2027","inicio":"10/12/2023"},
    {"nombre":"Zago, Oscar","distrito":"CIUDAD DE BUENOS AIRES","bloque":"MID - MOVIMIENTO DE INTEGRACIÓN Y DESARROLLO","mandato":"2023-2027","inicio":"10/12/2023"},
    {"nombre":"Zapata, Carlos Raúl","distrito":"SALTA","bloque":"LA LIBERTAD AVANZA","mandato":"2025-2029","inicio":"10/12/2025"},
    {"nombre":"Zaracho, Natalia","distrito":"BUENOS AIRES","bloque":"UNIÓN POR LA PATRIA","mandato":"2023-2027","inicio":"10/12/2023"},
    {"nombre":"Zigarán, María Inés","distrito":"JUJUY","bloque":"PROVINCIAS UNIDAS","mandato":"2025-2029","inicio":"10/12/2025"},
    {"nombre":"Zulli, Christian Alejandro","distrito":"CORRIENTES","bloque":"UNIÓN POR LA PATRIA","mandato":"2023-2027","inicio":"10/12/2023"},
]


def cargar_csv_local() -> list | None:
    if not os.path.exists(CSV_LOCAL_PATH):
        return None
    try:
        with open(CSV_LOCAL_PATH, newline="", encoding="utf-8-sig") as f:
            rows = list(csv.DictReader(f))
        if rows:
            log.info(f"CSV local cargado: {len(rows)} registros")
            return rows
    except Exception as e:
        log.warning(f"Error leyendo CSV local: {e}")
    return None


def get_data() -> list:
    local = cargar_csv_local()
    if local and len(local) > 10:
        return local
    return FALLBACK_DIPUTADOS


def contar_por_campo(data: list, campo: str) -> dict:
    counts: dict = {}
    for d in data:
        val = d.get(campo, "SIN DATOS")
        counts[val] = counts.get(val, 0) + 1
    return dict(sorted(counts.items(), key=lambda x: -x[1]))


def calcular_nep(data: list) -> float:
    total = len(data)
    if not total:
        return 0.0
    counts = contar_por_campo(data, "bloque")
    suma = sum((n / total) ** 2 for n in counts.values())
    return round(1 / suma, 2) if suma else 0.0


def calcular_fragmentacion(data: list) -> float:
    total = len(data)
    if not total:
        return 0.0
    counts = contar_por_campo(data, "bloque")
    return round(1 - sum((n / total) ** 2 for n in counts.values()), 4)


# ── Endpoints ──────────────────────────────────

@app.get("/diputados/listado")
def listado(
    distrito: Optional[str] = Query(None),
    bloque:   Optional[str] = Query(None),
    mandato:  Optional[str] = Query(None),
    q:        Optional[str] = Query(None),
):
    data = get_data()
    if distrito:
        data = [d for d in data if d.get("distrito","").upper() == distrito.upper()]
    if bloque:
        data = [d for d in data if d.get("bloque","").upper() == bloque.upper()]
    if mandato:
        data = [d for d in data if d.get("mandato","") == mandato]
    if q:
        ql = q.lower()
        data = [d for d in data if ql in f"{d.get('nombre','')} {d.get('bloque','')} {d.get('distrito','')}".lower()]
    return data


@app.get("/diputados/resumen")
def resumen():
    data = get_data()
    return {
        "total":         len(data),
        "por_bloque":    contar_por_campo(data, "bloque"),
        "por_distrito":  contar_por_campo(data, "distrito"),
        "por_mandato":   contar_por_campo(data, "mandato"),
        "nep":           calcular_nep(data),
        "fragmentacion": calcular_fragmentacion(data),
        "actualizacion": "2026-03-27",
    }


@app.get("/diputados/bloques")
def bloques():
    data  = get_data()
    total = len(data)
    return [{"bloque": b, "cantidad": n, "porcentaje": round(n/total*100,2)} for b,n in contar_por_campo(data,"bloque").items()]


@app.get("/diputados/distritos")
def distritos():
    data  = get_data()
    total = len(data)
    return [{"distrito": d, "cantidad": n, "porcentaje": round(n/total*100,2)} for d,n in contar_por_campo(data,"distrito").items()]


@app.get("/diputados/indicadores")
def indicadores():
    data  = get_data()
    total = len(data)
    n2529 = sum(1 for d in data if d.get("mandato") == "2025-2029")
    n2327 = sum(1 for d in data if d.get("mandato") == "2023-2027")
    dist  = contar_por_campo(data, "distrito")
    return {
        "total_diputados":        total,
        "bloques_activos":        len(contar_por_campo(data, "bloque")),
        "distritos":              len(dist),
        "mandato_2025_2029":      n2529,
        "mandato_2023_2027":      n2327,
        "tasa_renovacion_bienal": round(n2529/total,4) if total else 0,
        "nep":                    calcular_nep(data),
        "indice_fragmentacion":   calcular_fragmentacion(data),
        "distrito_mayor_bancas":  max(dist, key=dist.get) if dist else None,
        "distrito_menor_bancas":  min(dist, key=dist.get) if dist else None,
    }


@app.get("/diputados/buscar/{apellido}")
def buscar(apellido: str):
    data    = get_data()
    results = [d for d in data if apellido.lower() in d.get("nombre","").lower()]
    if not results:
        raise HTTPException(status_code=404, detail=f"No se encontraron diputados con '{apellido}'")
    return results


@app.get("/diputados/health")
def health():
    data = get_data()
    return {
        "status":    "ok",
        "total":     len(data),
        "fuente":    "csv_local" if cargar_csv_local() else "fallback_embebido",
        "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
    }