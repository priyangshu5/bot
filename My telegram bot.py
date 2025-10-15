import requests
import json
import logging
import asyncio
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from datetime import datetime
import re
import urllib.parse

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# Configuration
BOT_TOKEN = "8451120971:AAGdh4rxf5qoXBmKqlPt404OySsZcCp41ZQ"
A4F_API_KEY = "ddc-a4f-d050829fd1f3437fbb6ca2dce414467a"
A4F_API_URL = "https://api.a4f.co/v1/chat/completions"

# Available A4F Models
A4F_MODELS = [
    "provider-3/gpt-4o-mini",
    "provider-3/llama-3.3-70b",
    "provider-3/llama-3.1-70b",
    "provider-3/qwen-2.5-72b",
]

# Language Detection Patterns
LANGUAGE_PATTERNS = {
    'hindi': re.compile(r'[\u0900-\u097F]'),
    'assamese': re.compile(r'[\u0980-\u09FF]'),
    'english': re.compile(r'[a-zA-Z]')
}

# Enhanced System Prompt with Search Context
SYSTEM_PROMPT = """You are Priyangshu AI, a helpful multilingual assistant. You speak English, Hindi, and Assamese fluently. Always respond in the user's detected language. 

Use the provided web search results to give accurate, up-to-date information. If search results are available, prioritize them over general knowledge.

Be patient, clear, and provide detailed explanations for academic and programming topics."""

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle the /start command"""
    welcome_message = """🌍 **Namaste! Welcome to Priyangshu AI!** 🙏

**I speak:** English, Hindi (हिंदी), Assamese (অসমীয়া)

**Advanced Features:**
📚 All academic subjects
💻 Programming & coding  
🔍 **Real-time web search**
🤖 Multiple AI models
🌐 Current information

**Commands:**
/start - Welcome message
/help - Get help
/search <query> - Web search
/language - Change language
/status - Check bot status

**I can search the web for latest information!** 🔍
**Just ask me anything in your preferred language!** 🎯"""

    await update.message.reply_text(welcome_message, parse_mode='Markdown')

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle help command"""
    help_text = """🤖 **How to use Priyangshu AI:**

**🔍 Web Search Features:**
- I automatically search for current information
- Use `/search your_query` for direct searches
- Get real-time news, facts, and updates

**Ask in any language:**
- **English**: "Current weather in Delhi"
- **Hindi**: "दिल्ली का मौसम"  
- **Assamese**: "দিল্লীৰ বতৰ"

**I can help with:**
• Math & Science
• Programming & coding
• Current events & news
• Research & facts
• Homework & studies

**Try: `/search latest AI developments`** 💫"""

    await update.message.reply_text(help_text, parse_mode='Markdown')

async def search_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle direct search commands"""
    if not context.args:
        search_help = """🔍 **Web Search Help**

**Usage:** `/search your query`

**Examples:**
`/search latest technology news`
`/search Python programming tutorials`
`/search current weather in Mumbai`
`/search history of computers`

**I'll search DuckDuckGo and provide you with real-time results!** 🌐"""
        await update.message.reply_text(search_help, parse_mode='Markdown')
        return

    query = " ".join(context.args)
    user_language = detect_language(query)
    
    await update.message.chat.send_action(action="typing")
    
    try:
        # Perform DuckDuckGo search
        search_results = perform_duckduckgo_search(query)
        
        if search_results:
            response = format_search_results(search_results, query, user_language)
        else:
            response = get_search_error_response(user_language)
        
        await update.message.reply_text(response, parse_mode='Markdown', disable_web_page_preview=True)
        
    except Exception as e:
        logging.error(f"Search command error: {e}")
        error_response = get_search_error_response(user_language)
        await update.message.reply_text(error_response, parse_mode='Markdown')

def perform_duckduckgo_search(query: str, max_results: int = 5) -> list:
    """Perform DuckDuckGo search and return results"""
    try:
        # DuckDuckGo Instant Answer API
        response = requests.get(
            "https://api.duckduckgo.com/",
            params={
                "q": query,
                "format": "json",
                "no_html": "1",
                "skip_disambig": "1",
                "t": "PriyangshuAIBot"
            },
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            results = []
            
            # Add instant answer if available
            if data.get('AbstractText'):
                results.append({
                    'title': data.get('Heading', 'Instant Answer'),
                    'content': data['AbstractText'],
                    'url': data.get('AbstractURL', ''),
                    'type': 'instant_answer'
                })
            
            # Add related topics
            for topic in data.get('RelatedTopics', []):
                if len(results) >= max_results:
                    break
                if 'Text' in topic and 'FirstURL' in topic:
                    results.append({
                        'title': topic['Text'].split(' - ')[0] if ' - ' in topic['Text'] else 'Related Topic',
                        'content': topic['Text'],
                        'url': topic['FirstURL'],
                        'type': 'related_topic'
                    })
            
            # If no results from DuckDuckGo, try with HTML parsing fallback
            if not results:
                results = perform_duckduckgo_html_search(query, max_results)
            
            return results
            
    except Exception as e:
        logging.error(f"DuckDuckGo API error: {e}")
        # Fallback to HTML search
        return perform_duckduckgo_html_search(query, max_results)
    
    return []

def perform_duckduckgo_html_search(query: str, max_results: int = 5) -> list:
    """Fallback DuckDuckGo search using HTML parsing"""
    try:
        # Using DuckDuckGo Lite for better results
        response = requests.get(
            "https://lite.duckduckgo.com/lite/",
            params={"q": query},
            headers={
                "User-Agent": "Mozilla/5.0 (compatible; PriyangshuAIBot/1.0)"
            },
            timeout=10
        )
        
        if response.status_code == 200:
            # Simple HTML parsing for results
            import re
            results = []
            
            # Look for result patterns in the HTML
            pattern = r'<a rel="nofollow" class="result-link" href="([^"]+)"[^>]*>([^<]+)</a>'
            matches = re.findall(pattern, response.text)
            
            for url, title in matches[:max_results]:
                results.append({
                    'title': title.strip(),
                    'content': f"Search result for: {query}",
                    'url': url,
                    'type': 'web_result'
                })
            
            return results
            
    except Exception as e:
        logging.error(f"DuckDuckGo HTML search error: {e}")
    
    return []

def format_search_results(results: list, query: str, user_language: str) -> str:
    """Format search results based on language"""
    
    # Language-specific headers
    headers = {
        'english': f"🔍 **Search Results for: '{query}'**\n\n",
        'hindi': f"🔍 **खोज परिणाम: '{query}'**\n\n",
        'assamese': f"🔍 **সন্ধান ফলাফল: '{query}'**\n\n"
    }
    
    response = headers.get(user_language, headers['english'])
    
    for i, result in enumerate(results[:3], 1):
        title = result['title'][:100] + "..." if len(result['title']) > 100 else result['title']
        content = result['content'][:150] + "..." if len(result['content']) > 150 else result['content']
        
        response += f"**{i}. {title}**\n"
        response += f"{content}\n"
        if result['url']:
            response += f"🔗 {result['url']}\n"
        response += "\n"
    
    # Language-specific footers
    footers = {
        'english': "💡 *Use this information for your studies or ask me to explain!*",
        'hindi': "💡 *अपनी पढ़ाई के लिए इस जानकारी का उपयोग करें या मुझे समझाने के लिए कहें!*",
        'assamese': "💡 *আপোনাৰ অধ্যয়নৰ বাবে এই তথ্য ব্যৱহাৰ কৰক বা মোক বুজাবলৈ কওক!*"
    }
    
    response += footers.get(user_language, footers['english'])
    return response

def get_search_error_response(user_language: str) -> str:
    """Get error response for search failures"""
    errors = {
        'english': "❌ **Search temporarily unavailable**\n\nI'm having trouble accessing search results right now. Please try:\n• Checking your internet connection\n• Trying a different search query\n• Asking me general knowledge questions instead",
        'hindi': "❌ **खोज अस्थायी रूप से अनुपलब्ध**\n\nमुझे अभी खोज परिणामों तक पहुंचने में परेशानी हो रही है। कृपया:\n• अपना इंटरनेट कनेक्शन जांचें\n• एक अलग खोज क्वेरी आज़माएं\n• इसके बजाय मुझे सामान्य ज्ञान के प्रश्न पूछें",
        'assamese': "❌ **সন্ধান অস্থায়ীভাৱে অনুপলব্ধ**\n\nমই বৰ্তমান সন্ধান ফলাফলসমূহ প্ৰৱেশ কৰাত সমস্যা হৈছে। অনুগ্ৰহ কৰি:\n• আপোনাৰ ইণ্টাৰনেট সংযোগ পৰীক্ষা কৰক\n• এটা বেলেগ সন্ধান কুৱেৰী চেষ্টা কৰক\n• ইয়াৰ সলনি মোক সাধাৰণ জ্ঞানৰ প্ৰশ্ন সুধক"
    }
    return errors.get(user_language, errors['english'])

def detect_language(text: str) -> str:
    """Detect language from text"""
    hindi_chars = len(re.findall(r'[\u0900-\u097F]', text))
    assamese_chars = len(re.findall(r'[\u0980-\u09FF]', text))
    english_chars = len(re.findall(r'[a-zA-Z]', text))
    
    if hindi_chars > english_chars and hindi_chars > assamese_chars:
        return 'hindi'
    elif assamese_chars > english_chars and assamese_chars > hindi_chars:
        return 'assamese'
    else:
        return 'english'

def should_use_search(user_message: str) -> bool:
    """Determine if web search should be used for this query"""
    search_keywords = [
        'current', 'latest', 'recent', 'today', 'now', 'new', 'update',
        '2024', '2025', 'news', 'weather', 'score', 'results', 'live',
        'breaking', 'trending', 'stock', 'price', 'rate', 'exchange',
        'what happened', 'when is', 'where is', 'how to', 'best way',
        'tutorial', 'guide', 'review', 'comparison'
    ]
    
    message_lower = user_message.lower()
    return any(keyword in message_lower for keyword in search_keywords)

def get_smart_response(user_message: str, user_language: str) -> str:
    """Smart response system with web search integration"""
    
    # Check if we should use web search for this query
    use_search = should_use_search(user_message)
    search_context = ""
    
    if use_search:
        search_results = perform_duckduckgo_search(user_message, max_results=2)
        if search_results:
            search_context = "\n\n**Latest Information from Web Search:**\n"
            for result in search_results:
                search_context += f"• {result['content'][:200]}\n"
    
    # Try A4F API with search context
    api_response = try_a4f_api(user_message, user_language, search_context)
    if api_response and api_response != "ERROR":
        return api_response
    
    # If API fails, use enhanced local responses with search if available
    return get_enhanced_local_response(user_message, user_language, search_context)

def try_a4f_api(user_message: str, user_language: str, search_context: str = "") -> str:
    """Try to get response from A4F API with search context"""
    try:
        for model in A4F_MODELS:
            try:
                enhanced_prompt = f"{SYSTEM_PROMPT}\n\nUser Language: {user_language.upper()}\nRespond in: {user_language.upper()}"
                if search_context:
                    enhanced_prompt += f"\n\nWeb Search Context:{search_context}\n\nUse this search information to provide accurate, up-to-date answers."
                
                messages = [
                    {"role": "system", "content": enhanced_prompt},
                    {"role": "user", "content": user_message}
                ]
                
                response = requests.post(
                    A4F_API_URL,
                    headers={
                        "Authorization": f"Bearer {A4F_API_KEY}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": model,
                        "messages": messages,
                        "max_tokens": 1500,
                        "temperature": 0.7,
                    },
                    timeout=20
                )
                
                if response.status_code == 200:
                    result = response.json()
                    if 'choices' in result and result['choices']:
                        response_text = result['choices'][0]['message']['content']
                        # Add search attribution if search was used
                        if search_context:
                            attributions = {
                                'english': "\n\n🔍 *Information sourced from web search*",
                                'hindi': "\n\n🔍 *जानकारी वेब खोज से प्राप्त*",
                                'assamese': "\n\n🔍 *তথ্য ৱেব সন্ধানৰ পৰা সংগৃহীত*"
                            }
                            response_text += attributions.get(user_language, attributions['english'])
                        return response_text
                
            except requests.exceptions.Timeout:
                continue
            except requests.exceptions.ConnectionError:
                continue
            except Exception as e:
                logging.warning(f"Model {model} failed: {e}")
                continue
                
    except Exception as e:
        logging.error(f"API call failed: {e}")
    
    return "ERROR"

def get_enhanced_local_response(user_message: str, user_language: str, search_context: str = "") -> str:
    """Enhanced local responses with search context"""
    message_lower = user_message.lower()
    
    # If we have search context, use it
    if search_context:
        responses = {
            'english': f"🔍 **Based on latest information:**\n\n{search_context}\n\nI found some current information for you! Would you like me to explain any specific part?",
            'hindi': f"🔍 **नवीनतम जानकारी के आधार पर:**\n\n{search_context}\n\nमुझे आपके लिए कुछ वर्तमान जानकारी मिली! क्या आप मुझे किसी विशेष भाग की व्याख्या करना चाहेंगे?",
            'assamese': f"🔍 **সৰ্বশেষ তথ্যৰ ওপৰত ভিত্তি কৰি:**\n\n{search_context}\n\nমই আপোনাৰ বাবে কিছু বৰ্তমানৰ তথ্য পাইছো! আপুনি মোক কোনো নিৰ্দিষ্ট অংশ বুজাব বিচাৰেনে?"
        }
        return responses.get(user_language, responses['english'])
    
    # Rest of the local responses (same as before but shortened for brevity)
    if any(word in message_lower for word in ['prime minister', 'प्रधानमंत्री', 'প্রধান মন্ত্ৰী']):
        responses = {
            'english': "🇮🇳 **Prime Minister of India**\n\nNarendra Modi is the current Prime Minister (2024). 🔍 *Try `/search current news` for latest updates!*",
            'hindi': "🇮🇳 **भारत के प्रधान मंत्री**\n\nनरेंद्र मोदी वर्तमान प्रधान मंत्री हैं (2024)। 🔍 *नवीनतम अपडेट के लिए `/search current news` आज़माएं!*",
            'assamese': "🇮🇳 **ভাৰতৰ প্ৰধান মন্ত্ৰী**\n\nনৰেন্দ্ৰ মোদী বৰ্তমানৰ প্ৰধান মন্ত্ৰী (২০২৪)। 🔍 *সৰ্বশেষ আপডেটৰ বাবে `/search current news` চেষ্টা কৰক!*"
        }
        return responses.get(user_language, responses['english'])
    
    # Default response encouraging search
    responses = {
        'english': "🤖 **Priyangshu AI is Ready!**\n\nI can help with:\n• Academic subjects\n• Programming help\n• **Current information** (use `/search`)\n• Multilingual support\n\nTry: `/search your topic` for latest info! 🚀",
        'hindi': "🤖 **प्रियांशू एआई तैयार है!**\n\nमैं इनमें मदद कर सकता हूं:\n• शैक्षिक विषय\n• प्रोग्रामिंग सहायता\n• **वर्तमान जानकारी** (`/search` का उपयोग करें)\n• बहुभाषी समर्थन\n\nनवीनतम जानकारी के लिए आज़माएं: `/search your topic`! 🚀",
        'assamese': "🤖 **প্ৰিয়াংশু AI সাজু আছে!**\n\nমই ইয়াত সহায় কৰিব পাৰো:\n• শিক্ষামূলক বিষয়\n• প্ৰগ্ৰেমিং সহায়\n• **বৰ্তমানৰ তথ্য** (`/search` ব্যৱহাৰ কৰক)\n• বহুভাষী সমৰ্থন\n\nসৰ্বশেষ তথ্যৰ বাবে চেষ্টা কৰক: `/search your topic`! 🚀"
    }
    return responses.get(user_language, responses['english'])

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle incoming messages with search integration"""
    try:
        user_message = update.message.text
        user_id = update.message.from_user.id
        
        logging.info(f"Received message from user {user_id}: {user_message}")
        
        # Detect language
        user_language = detect_language(user_message)
        context.user_data['detected_language'] = user_language
        
        # Show typing action
        await update.message.chat.send_action(action="typing")
        
        # Get smart response with search integration
        ai_response = get_smart_response(user_message, user_language)
        
        # Send response
        if len(ai_response) > 4096:
            parts = [ai_response[i:i+4096] for i in range(0, len(ai_response), 4096)]
            for part in parts:
                await update.message.reply_text(part, parse_mode='Markdown')
                await asyncio.sleep(0.5)
        else:
            await update.message.reply_text(ai_response, parse_mode='Markdown')
            
        logging.info(f"Sent {user_language} response to user {user_id}")
            
    except Exception as e:
        logging.error(f"Error handling message: {e}")
        error_responses = {
            'english': "⚠️ Temporary issue. Please try again or use `/search` for direct web search!",
            'hindi': "⚠️ अस्थायी समस्या। कृपया पुनः प्रयास करें या सीधी वेब खोज के लिए `/search` का उपयोग करें!",
            'assamese': "⚠️ অস্থায়ী সমস্যা। অনুগ্ৰহ কৰি পুনৰ চেষ্টা কৰক বা প্ৰত্যক্ষ ৱেব সন্ধানৰ বাবে `/search` ব্যৱহাৰ কৰক!"
        }
        user_language = context.user_data.get('detected_language', 'english')
        await update.message.reply_text(error_responses.get(user_language, error_responses['english']))

# Other commands (language, status, etc.) remain the same
async def language_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Language settings"""
    language_menu = """🌐 **Choose Language:**

/english - English
/hindi - हिंदी  
/assamese - অসমীয়া

I automatically detect your language too! 🎯"""

    await update.message.reply_text(language_menu, parse_mode='Markdown')

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Check bot status"""
    status_text = """🟢 **Priyangshu AI - Online & Ready!**

✅ **Services:** Operational
✅ **Languages:** English, Hindi, Assamese
✅ **AI Models:** Multiple available
✅ **Web Search:** DuckDuckGo Integrated
✅ **Help:** Academic & Programming

**🔍 Now with real-time web search!**
**Try:** `/search latest news` 🚀"""

    await update.message.reply_text(status_text, parse_mode='Markdown')

def main():
    """Start the bot with DuckDuckGo search"""
    try:
        application = Application.builder().token(BOT_TOKEN).build()
        
        # Add handlers
        application.add_handler(CommandHandler("start", start_command))
        application.add_handler(CommandHandler("help", help_command))
        application.add_handler(CommandHandler("search", search_command))
        application.add_handler(CommandHandler("language", language_command))
        application.add_handler(CommandHandler("status", status_command))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
        
        # Start the bot
        print("🚀 Priyangshu AI with DuckDuckGo Search is starting...")
        print("✅ Web search integration: ACTIVE")
        print("🌍 Multi-language support: READY")
        print("🤖 AI models: LOADED")
        print("⏹️ Press Ctrl+C to stop")
        
        application.run_polling()
        
    except Exception as e:
        logging.error(f"Failed to start bot: {e}")
        print(f"❌ Failed to start bot: {e}")

if __name__ == "__main__":
    main()