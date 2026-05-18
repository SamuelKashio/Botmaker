# 💬 chat_analyzer.py
# ───────────────────────────────────────────────────────────
# Módulo de análisis de chats SIN IA
# Copiar este archivo a tu proyecto y usarlo
# ───────────────────────────────────────────────────────────

import pandas as pd
import numpy as np
from collections import Counter, defaultdict
from textblob import TextBlob
import nltk
from nltk.corpus import stopwords
from typing import List, Dict, Tuple
import streamlit as st

# Descargar recursos NLTK una sola vez
try:
    nltk.data.find('corpora/stopwords')
except LookupError:
    with st.spinner("Descargando recursos NLTK..."):
        nltk.download('stopwords')
        nltk.download('punkt')


# ═══════════════════════════════════════════════════════════
# CONFIGURACIÓN: Palabras clave por categoría
# ═══════════════════════════════════════════════════════════

CHAT_CATEGORIES = {
    '💳 Facturación': [
        'factura', 'boleta', 'pago', 'cobro', 'comprobante', 'recibo',
        'impuesto', 'iva', 'total', 'monto', 'deuda', 'facturación',
        'invoice', 'billing'
    ],
    '⚙️ Técnico': [
        'error', 'no funciona', 'fallo', 'crash', 'problema', 'bug',
        'no responde', 'lentitud', 'desconexión', 'fallar',
        'failure', 'malfunction', 'glitch', 'slow'
    ],
    '📦 Producto': [
        'precio', 'características', 'especificaciones', 'modelo',
        'color', 'tamaño', 'material', 'producto', 'item', 'artículo',
        'detalles', 'features', 'description', 'calidad'
    ],
    '🚚 Envío/Entrega': [
        'envío', 'entrega', 'paquete', 'dirección', 'tracking',
        'despachado', 'llegó', 'recibir', 'demora', 'retraso',
        'shipping', 'delivery', 'address', 'package', 'location'
    ],
    '🔄 Devolución': [
        'devolver', 'cambio', 'rembolso', 'retorno', 'garantía',
        'reclamo', 'defectuoso', 'devuelto', 'return', 'refund',
        'warranty', 'exchange', 'broken'
    ],
    '👤 Cuenta/Acceso': [
        'usuario', 'contraseña', 'login', 'sesión', 'perfil', 'datos',
        'cuenta', 'acceso', 'password', 'account', 'profile', 'reset',
        'registrar', 'crear cuenta'
    ],
    '💬 Consulta': [
        'consulta', 'pregunta', 'información', 'dudas', 'horario',
        'contacto', 'ubicación', 'teléfono', 'help', 'support',
        'saber', 'cómo', 'dónde', 'cuándo'
    ],
}

# Stop words extendidos
EXTENDED_STOP_WORDS = {
    'el', 'la', 'de', 'que', 'y', 'a', 'en', 'un', 'ser', 'se',
    'no', 'haber', 'por', 'con', 'su', 'para', 'es', 'lo', 'como',
    'más', 'o', 'poder', 'decir', 'este', 'ir', 'otro', 'ese',
    'si', 'me', 'ya', 'ver', 'porque', 'dar', 'cuando', 'he', 'ha',
    'donde', 'han', 'quien', 'están', 'estado', 'desde', 'todo',
    'durante', 'todos', 'uno', 'les', 'ni', 'contra', 'otros',
    'fueron', 'eso', 'había', 'ante', 'ellos', 'estaba', 'estaban',
}


# ═══════════════════════════════════════════════════════════
# CLASE PRINCIPAL
# ═══════════════════════════════════════════════════════════

class ChatAnalyzer:
    """Análisis de chats sin IA - 100% gratis"""
    
    def __init__(self):
        try:
            self.stop_words = set(stopwords.words('spanish')) | EXTENDED_STOP_WORDS
        except:
            self.stop_words = EXTENDED_STOP_WORDS
    
    def categorize_chat(self, text: str) -> Tuple[str, float]:
        """Detectar categoría basada en palabras clave"""
        if not text:
            return '❓ Desconocido', 0.0
        
        text_lower = text.lower()
        scores = {}
        
        for category, keywords in CHAT_CATEGORIES.items():
            score = sum(text_lower.count(kw.lower()) for kw in keywords)
            scores[category] = score
        
        best_category = max(scores, key=scores.get)
        max_score = scores[best_category]
        total_score = sum(scores.values())
        confidence = (max_score / total_score) if total_score > 0 else 0.0
        
        if max_score == 0:
            return '❓ Desconocido', 0.0
        
        return best_category, round(confidence, 2)
    
    def analyze_sentiment(self, text: str) -> Dict:
        """Análisis simple de sentimiento"""
        if not text:
            return {'sentiment': 'Neutro', 'score': 0.0, 'emoji': '🟡'}
        
        try:
            blob = TextBlob(text)
            polarity = blob.sentiment.polarity
        except:
            return {'sentiment': 'Neutro', 'score': 0.0, 'emoji': '🟡'}
        
        if polarity > 0.1:
            sentiment, emoji = 'Positivo', '🟢'
        elif polarity < -0.1:
            sentiment, emoji = 'Negativo', '🔴'
        else:
            sentiment, emoji = 'Neutro', '🟡'
        
        return {'sentiment': sentiment, 'score': round(polarity, 2), 'emoji': emoji}
    
    def extract_keywords(self, text: str, top_n: int = 5) -> List[Tuple[str, int]]:
        """Extraer palabras clave más frecuentes"""
        if not text:
            return []
        
        try:
            words = nltk.word_tokenize(text.lower())
        except:
            words = text.lower().split()
        
        words = [
            word for word in words
            if (word.isalnum() and word not in self.stop_words 
                and len(word) > 2 and not word.isdigit())
        ]
        
        word_freq = Counter(words)
        return word_freq.most_common(top_n)
    
    def classify_resolution_time(self, created_at, closed_at) -> Dict:
        """Clasificar velocidad de resolución"""
        if pd.isna(closed_at):
            return {
                'status': 'Abierto',
                'time_hours': None,
                'category': 'Pendiente',
                'emoji': '⏳'
            }
        
        try:
            time_diff = (pd.Timestamp(closed_at) - pd.Timestamp(created_at)).total_seconds() / 3600
        except:
            return {'status': 'Error', 'time_hours': None, 'category': 'Desconocido', 'emoji': '❌'}
        
        if time_diff < 1:
            return {'status': 'Cerrado', 'time_hours': round(time_diff, 1), 'category': 'Muy rápido', 'emoji': '🟢'}
        elif time_diff < 4:
            return {'status': 'Cerrado', 'time_hours': round(time_diff, 1), 'category': 'Rápido', 'emoji': '🟢'}
        elif time_diff < 24:
            return {'status': 'Cerrado', 'time_hours': round(time_diff, 1), 'category': 'Normal', 'emoji': '🟡'}
        else:
            return {'status': 'Cerrado', 'time_hours': round(time_diff, 1), 'category': 'Lento', 'emoji': '🔴'}
    
    def summarize_chat(self, messages: List[Dict]) -> Dict:
        """Resumen completo de un chat"""
        if not messages:
            return {}
        
        all_text = ' '.join([msg.get('content', '') for msg in messages if msg.get('content')])
        user_text = ' '.join([msg.get('content', '') for msg in messages if msg.get('from') == 'user' and msg.get('content')])
        agent_text = ' '.join([msg.get('content', '') for msg in messages if msg.get('from') == 'agent' and msg.get('content')])
        
        category, confidence = self.categorize_chat(all_text)
        sentiment = self.analyze_sentiment(all_text)
        keywords = self.extract_keywords(all_text, top_n=5)
        
        return {
            'total_messages': len(messages),
            'user_messages': sum(1 for m in messages if m.get('from') == 'user'),
            'agent_messages': sum(1 for m in messages if m.get('from') == 'agent'),
            'category': category,
            'category_confidence': confidence,
            'sentiment': sentiment['sentiment'],
            'sentiment_score': sentiment['score'],
            'sentiment_emoji': sentiment['emoji'],
            'keywords': keywords,
            'avg_message_length': round(np.mean([len(m.get('content', '')) for m in messages if m.get('content')])) if messages else 0,
            'user_sentiment': self.analyze_sentiment(user_text)['sentiment'],
            'agent_sentiment': self.analyze_sentiment(agent_text)['sentiment'],
        }
    
    def analyze_bulk(self, df_sessions: pd.DataFrame, df_messages: pd.DataFrame) -> Dict:
        """Analizar todos los chats y extraer tendencias"""
        
        results = {
            'total_chats': 0,
            'categories': defaultdict(int),
            'sentiments': {'Positivo': 0, 'Negativo': 0, 'Neutro': 0},
            'keywords': Counter(),
            'resolution_times': defaultdict(int),
            'avg_sentiment_score': [],
            'chat_summaries': [],
        }
        
        for idx, session in df_sessions.iterrows():
            session_id = session['id']
            chat_messages = df_messages[df_messages['chat_id'] == session_id]
            
            if chat_messages.empty:
                continue
            
            messages = [
                {'from': 'user' if row['from'] == 'user' else 'agent', 'content': row['content']}
                for _, row in chat_messages.iterrows()
            ]
            
            summary = self.summarize_chat(messages)
            
            results['total_chats'] += 1
            
            category = summary['category']
            results['categories'][category] += 1
            
            sentiment = summary['sentiment']
            results['sentiments'][sentiment] += 1
            results['avg_sentiment_score'].append(summary['sentiment_score'])
            
            for word, freq in summary['keywords']:
                results['keywords'][word] += freq
            
            res_time = self.classify_resolution_time(session['createdAt'], session.get('closedAt'))
            results['resolution_times'][res_time['category']] += 1
            
            if len(results['chat_summaries']) < 30:
                results['chat_summaries'].append({
                    'session_id': session_id,
                    'category': category,
                    'sentiment': sentiment,
                    'emoji': summary['sentiment_emoji'],
                    'top_keyword': summary['keywords'][0][0] if summary['keywords'] else 'N/A'
                })
        
        if results['avg_sentiment_score']:
            results['avg_sentiment_score'] = round(np.mean(results['avg_sentiment_score']), 2)
        else:
            results['avg_sentiment_score'] = 0.0
        
        results['keywords'] = dict(results['keywords'].most_common(15))
        
        return results


# ═══════════════════════════════════════════════════════════
# FUNCIÓN PARA STREAMLIT (copia directa en tu tab)
# ═══════════════════════════════════════════════════════════

@st.cache_resource
def get_analyzer():
    """Cache el analizador"""
    return ChatAnalyzer()


def render_chat_analysis(df_sessions: pd.DataFrame, df_messages: pd.DataFrame):
    """
    Renderizar análisis de chats en Streamlit
    
    Uso en botmaker_dashboard.py:
    ─────────────────────────────
    from chat_analyzer import render_chat_analysis
    
    with tab_analysis:
        render_chat_analysis(df_sessions, df_messages)
    """
    
    if df_sessions.empty or df_messages.empty:
        st.info("📊 Sin datos para analizar")
        return
    
    analyzer = get_analyzer()
    
    with st.spinner("Analizando chats..."):
        results = analyzer.analyze_bulk(df_sessions, df_messages)
    
    # ─── Métricas ───
    st.subheader("📈 Resumen General")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Total Chats", results['total_chats'])
    
    with col2:
        positive_pct = (results['sentiments']['Positivo'] / results['total_chats'] * 100) if results['total_chats'] > 0 else 0
        st.metric("Positivos", f"{positive_pct:.0f}%", f"{results['sentiments']['Positivo']} chats")
    
    with col3:
        negative_pct = (results['sentiments']['Negativo'] / results['total_chats'] * 100) if results['total_chats'] > 0 else 0
        st.metric("Negativos", f"{negative_pct:.0f}%", f"{results['sentiments']['Negativo']} chats")
    
    with col4:
        st.metric("Sentimiento Promedio", f"{results['avg_sentiment_score']}", "-1 a +1")
    
    # ─── Gráficos ───
    st.subheader("📊 Distribuciones")
    
    col_a, col_b = st.columns(2)
    
    with col_a:
        st.write("**Categorías de Chats**")
        categories_df = pd.DataFrame([
            {'Categoría': cat, 'Cantidad': count}
            for cat, count in results['categories'].items()
        ]).sort_values('Cantidad', ascending=False)
        
        if not categories_df.empty:
            st.bar_chart(categories_df.set_index('Categoría')['Cantidad'], use_container_width=True)
    
    with col_b:
        st.write("**Sentimientos**")
        sentiments_df = pd.DataFrame([
            {'Sentimiento': k, 'Cantidad': v}
            for k, v in results['sentiments'].items()
        ])
        
        if not sentiments_df.empty:
            st.bar_chart(sentiments_df.set_index('Sentimiento')['Cantidad'], use_container_width=True)
    
    # ─── Palabras clave ───
    st.subheader("🔑 Palabras Clave Frecuentes")
    
    keywords_df = pd.DataFrame([
        {'Palabra': word, 'Frecuencia': freq}
        for word, freq in results['keywords'].items()
    ]).sort_values('Frecuencia', ascending=False)
    
    if not keywords_df.empty:
        st.dataframe(keywords_df, use_container_width=True, hide_index=True)
    
    # ─── Tiempo de resolución ───
    st.subheader("⏱️ Velocidad de Resolución")
    
    resolution_df = pd.DataFrame([
        {'Categoría': k, 'Chats': v}
        for k, v in results['resolution_times'].items()
        if k != 'Pendiente'
    ])
    
    if not resolution_df.empty:
        st.bar_chart(resolution_df.set_index('Categoría')['Chats'], use_container_width=True)
    
    # ─── Ejemplos ───
    st.subheader("📋 Últimos Chats Analizados")
    
    examples_df = pd.DataFrame(results['chat_summaries'])
    
    if not examples_df.empty:
        st.dataframe(
            examples_df[[
                'session_id', 'emoji', 'category', 'sentiment', 'top_keyword'
            ]].rename(columns={
                'session_id': 'Chat ID',
                'emoji': '',
                'category': 'Categoría',
                'sentiment': 'Sentimiento',
                'top_keyword': 'Palabra Clave'
            }),
            use_container_width=True,
            hide_index=True
        )
    
    # ─── Insights ───
    st.subheader("💡 Insights Automáticos")
    
    col_i1, col_i2, col_i3 = st.columns(3)
    
    with col_i1:
        if results['sentiments']['Negativo'] > results['total_chats'] * 0.3:
            st.warning(
                f"⚠️ {results['sentiments']['Negativo']} chats negativos\n\n"
                "Más de 30% tienen sentimiento negativo."
            )
        else:
            st.success(
                f"✅ Sentimiento positivo\n\n"
                f"{results['sentiments']['Positivo']} de {results['total_chats']} chats positivos"
            )
    
    with col_i2:
        if results['categories']:
            most_common = max(results['categories'].items(), key=lambda x: x[1])
            st.info(
                f"📌 Categoría más frecuente\n\n"
                f"{most_common[0]}\n"
                f"{most_common[1]} chats ({most_common[1]/results['total_chats']*100:.0f}%)"
            )
    
    with col_i3:
        slow_chats = results['resolution_times'].get('Lento', 0)
        if slow_chats > 0:
            st.error(
                f"🔴 {slow_chats} chats lentos\n\n"
                "Más de 24 horas para resolver."
            )
        else:
            st.success(
                "✅ Todos rápidos\n\n"
                "Sin demoras importantes"
            )
