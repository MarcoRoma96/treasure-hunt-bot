import logging
import json
import hashlib
import os
import qrcode
from io import BytesIO
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

class TreasureHuntBot:
    def __init__(self, token: str):
        self.token = token
        self.game_data = {}  # In production, use a database
        self.riddles = self.load_riddles()
        self.qr_codes = self.generate_qr_codes()
        
    def load_riddles(self) -> List[Dict]:
        """Load riddles and their locations. Customize this for your event."""
        # You can easily add or remove riddles here to change the number of stops
        return [
                        {
                "id": 0,
                "riddle": "🧠 Warm-up! What building has the most stories?",
                "answer": "library",
                "hint": "Think about books!",
                "image_path": "img_riddles/riddle_0.jpg",
                "map_path": "img_maps/map_1.jpg",
                "location": "start",
                "qr_code": "N/A"  # Ignorato per tappa 0
            },
            {
                "id": 1,
                "riddle": "🌳 Under the shade...",
                "answer": "park",
                "hint": "...",
                "image_path": "...",
                "map_path": "img_maps/map_2.jpg",
                "location": "park",
                "qr_code": "TREASURE_HUNT_LOC_1_PARK"
            },
            {
                "id": 3,
                "riddle": "☕ Where caffeine flows and friends meet, aromatic beans make life complete. Find the place where morning starts sweet.",
                "location": "cafe",
                "hint": "The smell of fresh coffee guides the way!",
                "image_path": "img_riddles/riddle_3.jpg",
                "qr_code": "TREASURE_HUNT_LOC_3_CAFE"
            },
            {
                "id": 4,
                "riddle": "🏆 The final treasure lies within, where this hunt began. Show your courage, you've nearly won!",
                "location": "start",
                "hint": "Return to where your journey began!",
                "image_path": "img_riddles/riddle_4.jpg",
                "qr_code": "TREASURE_HUNT_LOC_4_START"
            }
            # Add more riddles here for more stops:
            # {
            #     "id": 5,
            #     "riddle": "Your next riddle here...",
            #     "location": "location_name",
            #     "hint": "Your hint here...",
            #     "image_path": "img_riddles/riddle_1.jpg",
            #     "qr_code": "TREASURE_HUNT_LOC_5_LOCATION_NAME"
            # }
        ]
    
    def generate_qr_codes(self) -> Dict[str, str]:
        """Generate QR codes for each location."""
        qr_codes = {}
        for riddle in self.riddles:
            qr = qrcode.QRCode(version=1, box_size=10, border=5)
            qr.add_data(riddle["qr_code"])
            qr.make(fit=True)
            qr_codes[riddle["qr_code"]] = qr
        return qr_codes
    
    def save_qr_code_images(self, output_dir: str = "qr_codes"):
        """Save QR code images to files for printing."""
        import os
        
        # Create output directory if it doesn't exist
        os.makedirs(output_dir, exist_ok=True)
        
        for i, riddle in enumerate(self.riddles, 1):
            qr_code_data = riddle["qr_code"]
            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_L,
                box_size=10,
                border=4,
            )
            qr.add_data(qr_code_data)
            qr.make(fit=True)
            
            # Create QR code image
            img = qr.make_image(fill_color="black", back_color="white")
            
            # Save with descriptive filename
            filename = f"stop_{i:02d}_{riddle['location']}.png"
            filepath = os.path.join(output_dir, filename)
            img.save(filepath)
            
            print(f"✅ Generated QR code for Stop {i} ({riddle['location']}): {filepath}")
        
        print(f"\n🎯 Total QR codes generated: {len(self.riddles)}")
        print(f"📁 Files saved in: {output_dir}/")
        
        # Also create a summary file
        summary_path = os.path.join(output_dir, "qr_codes_summary.txt")
        with open(summary_path, 'w') as f:
            f.write("TREASURE HUNT QR CODES SUMMARY\n")
            f.write("=" * 50 + "\n\n")
            for i, riddle in enumerate(self.riddles, 1):
                f.write(f"Stop {i}: {riddle['location'].upper()}\n")
                f.write(f"QR Code Data: {riddle['qr_code']}\n")
                f.write(f"Riddle: {riddle['riddle']}\n")
                f.write(f"Hint: {riddle['hint']}\n")
                f.write(f"File: stop_{i:02d}_{riddle['location']}.png\n")
                f.write("-" * 30 + "\n")
        
        print(f"📋 Summary saved to: {summary_path}")
        return True
    
    def create_game_session(self, chat_id: int, team_name: str) -> Dict:
        """Create a new game session for a team."""
        session = {
            "team_name": team_name,
            "current_riddle": 0,
            "start_time": datetime.now(),
            "completed_riddles": [],
            "hints_used": 0,
            "status": "active"
        }
        self.game_data[chat_id] = session
        return session
    
    def get_current_riddle(self, chat_id: int) -> Optional[Dict]:
        """Get the current riddle for a team."""
        if chat_id not in self.game_data:
            return None
        
        session = self.game_data[chat_id]
        if session["current_riddle"] >= len(self.riddles):
            return None
        
        return self.riddles[session["current_riddle"]]
    
    def validate_qr_code(self, chat_id: int, qr_data: str) -> bool:
        """Validate if the scanned QR code is correct for current riddle."""
        current_riddle = self.get_current_riddle(chat_id)
        if not current_riddle:
            return False
        
        return qr_data == current_riddle["qr_code"]
    
    def advance_riddle(self, chat_id: int) -> bool:
        """Advance to the next riddle."""
        if chat_id not in self.game_data:
            return False
        
        session = self.game_data[chat_id]
        session["completed_riddles"].append(session["current_riddle"])
        session["current_riddle"] += 1
        
        if session["current_riddle"] >= len(self.riddles):
            session["status"] = "completed"
            session["end_time"] = datetime.now()
        
        return True
    
    def get_leaderboard(self) -> List[Dict]:
        """Get the leaderboard of completed games."""
        completed_games = []
        for chat_id, session in self.game_data.items():
            if session["status"] == "completed":
                duration = session["end_time"] - session["start_time"]
                completed_games.append({
                    "team_name": session["team_name"],
                    "duration": duration,
                    "hints_used": session["hints_used"],
                    "chat_id": chat_id
                })
        
        # Sort by duration (fastest first), then by hints used (fewer is better)
        completed_games.sort(key=lambda x: (x["duration"], x["hints_used"]))
        return completed_games


async def send_riddle(context, bot_instance, chat_id: int, team_name: str = None):
    current_riddle = bot_instance.get_current_riddle(chat_id)
    if not current_riddle:
        await context.bot.send_message(chat_id=chat_id, text="❌ No active riddle found.")
        return

    keyboard = [[InlineKeyboardButton("💡 Get Hint", callback_data="hint")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    riddle_text = ""
    if team_name:
        riddle_text += f"🎯 **Team:** {team_name}\n\n"
    else:
        riddle_text += f"✅ **Great job!** Location found!\n\n"

    riddle_text += f"🧩 **Riddle #{current_riddle['id']}:**\n{current_riddle['riddle']}\n\n"
    riddle_text += "Find the location and scan the QR code there!"

    # 📸 Invia immagine se presente e se il file esiste
    image_path = current_riddle.get("image_path")
    if image_path and os.path.isfile(image_path):
        try:
            with open(image_path, "rb") as img:
                await context.bot.send_photo(chat_id=chat_id, photo=img)
        except Exception as e:
            await context.bot.send_message(chat_id=chat_id, text="⚠️ Could not load image for this riddle.")
    else:
        # Log utile per il debug (facoltativo)
        logger.info(f"No image found for riddle {current_riddle['id']} (image_path: {image_path})")

    # 🧩 Invia il testo dell'indovinello
    await context.bot.send_message(chat_id=chat_id, text=riddle_text, reply_markup=reply_markup, parse_mode='Markdown')




# Bot command handlers
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start command handler."""
    keyboard = [
        [InlineKeyboardButton("🎮 Start New Game", callback_data="new_game")],
        [InlineKeyboardButton("📊 Leaderboard", callback_data="leaderboard")],
        [InlineKeyboardButton("ℹ️ How to Play", callback_data="help")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    welcome_text = """
🏴‍☠️ **Welcome to the Treasure Hunt!** 🏴‍☠️

Ready for an adventure? This is a QR code-based treasure hunt game where you'll solve riddles and find locations around the event!

**How it works:**
1. Start a new game and register your team
2. Receive your first riddle
3. Solve the riddle to find a location
4. Scan the QR code at that location
5. Get your next riddle and repeat!

Good luck, treasure hunters! 🗺️✨
    """
    
    await update.message.reply_text(welcome_text, reply_markup=reply_markup, parse_mode='Markdown')

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle button callbacks."""
    query = update.callback_query
    await query.answer()
    
    bot_instance = context.bot_data.get('bot_instance')
    if not bot_instance:
        await query.edit_message_text("❌ Bot not properly initialized. Please restart.")
        return
    
    if query.data == "new_game":
        await query.edit_message_text("🎯 Please enter your team name:")
        context.user_data['waiting_for_team_name'] = True
    
    elif query.data == "leaderboard":
        leaderboard = bot_instance.get_leaderboard()
        if not leaderboard:
            await query.edit_message_text("📊 No completed games yet! Be the first to finish! 🏆")
            return
        
        leaderboard_text = "🏆 **LEADERBOARD** 🏆\n\n"
        for i, game in enumerate(leaderboard[:10], 1):
            duration_str = str(game["duration"]).split('.')[0]  # Remove microseconds
            leaderboard_text += f"{i}. **{game['team_name']}**\n"
            leaderboard_text += f"   ⏱️ Time: {duration_str}\n"
            leaderboard_text += f"   💡 Hints used: {game['hints_used']}\n\n"
        
        await query.edit_message_text(leaderboard_text, parse_mode='Markdown')
    
    elif query.data == "help":
        help_text = """
📖 **How to Play the Treasure Hunt**

1. **Start a Game**: Register your team name
2. **Read the Riddle**: Each riddle points to a location
3. **Find the Location**: Use the riddle clues to find where to go
4. **Scan QR Code**: Once there, scan the QR code to confirm your arrival
5. **Next Riddle**: Get your next challenge!

**Tips:**
- Work as a team to solve riddles faster
- Use hints sparingly - they affect your leaderboard position
- QR codes are hidden at each location
- Have fun exploring! 🎉

**Commands:**
- /start - Return to main menu
- /hint - Get a hint for current riddle
- /status - Check your current progress
        """
        await query.edit_message_text(help_text, parse_mode='Markdown')
    
    elif query.data == "hint":
        current_riddle = bot_instance.get_current_riddle(query.message.chat_id)
        if current_riddle:
            bot_instance.game_data[query.message.chat_id]["hints_used"] += 1
            await query.edit_message_text(f"💡 **Hint:** {current_riddle['hint']}")
        else:
            await query.edit_message_text("❌ No active riddle to get a hint for!")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    bot_instance = context.bot_data.get('bot_instance')
    if not bot_instance:
        await update.message.reply_text("❌ Bot not properly initialized. Please restart.")
        return
    
    chat_id = update.message.chat_id
    text = update.message.text.strip().lower()
    
    # Check if waiting for team name
    if context.user_data.get('waiting_for_team_name'):
        team_name = text.strip()
        if len(team_name) < 2:
            await update.message.reply_text("❌ Team name must be at least 2 characters long!")
            return
        ## TODO: CHECK IF TEAM NAME ALREADY EXISTS
        ## TODO: CHECK IF TEAM NAME IS VALID AND NOT OFFENSIVE

        bot_instance.create_game_session(chat_id, team_name)
        context.user_data['waiting_for_team_name'] = False

        # Invia il primo riddle (tappa 0)
        await send_riddle(context, bot_instance, chat_id, team_name)
        return

    # Check if it's a QR code
    if text.startswith("TREASURE_HUNT_"):
        # CHECK answered riddle before next QR
        if current_riddle["id"] == 0:
            await update.message.reply_text("🔐 Devi prima rispondere all'indovinello iniziale!")
            return

        if bot_instance.validate_qr_code(chat_id, text):
            # Avanza al prossimo riddle (da QR)
            bot_instance.advance_riddle(chat_id)

            session = bot_instance.game_data.get(chat_id)
            if session["status"] == "completed":
                duration = session["end_time"] - session["start_time"]
                await update.message.reply_text(
                    f"🏆 *CONGRATULAZIONI*\nHai completato la caccia al tesoro!\n⏱️ Tempo: {str(duration).split('.')[0]}\n💡 Suggerimenti: {session['hints_used']}",
                    parse_mode="Markdown"
                )
                return

            # Invia nuovo riddle
            await send_riddle(context, bot_instance, chat_id)
        else:
            await update.message.reply_text("❌ QR code non valido per questa tappa.")
        return

    # Altrimenti, si tratta di una risposta testuale a un riddle
    session = bot_instance.game_data.get(chat_id)
    if not session or session["status"] != "active":
        await update.message.reply_text("❌ Nessuna partita attiva. Usa /start per iniziare.")
        return

    current_riddle = bot_instance.get_current_riddle(chat_id)
    if not current_riddle:
        await update.message.reply_text("✅ Hai già risolto tutti gli enigmi!")
        return

    correct_answer = current_riddle.get("answer", "").strip().lower()
    if text == correct_answer:
        # Risposta corretta → invia mappa per raggiungere tappa successiva
        map_path = current_riddle.get("map_path")
        if map_path and os.path.isfile(map_path):
            with open(map_path, "rb") as f:
                await update.message.reply_photo(
                    photo=f,
                    caption="🗺️ Ottimo! Ecco dove andare. Raggiungi il luogo e scansiona il QR per ricevere il prossimo enigma."
                )
        else:
            await update.message.reply_text("✅ Risposta corretta! Raggiungi la prossima tappa e scansiona il QR.")

    else:
        await update.message.reply_text("❌ Risposta sbagliata. Riprova o usa /hint.")


async def hint_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Provide hint for current riddle."""
    bot_instance = context.bot_data.get('bot_instance')
    if not bot_instance:
        await update.message.reply_text("❌ Bot not properly initialized. Please restart.")
        return
    
    chat_id = update.message.chat_id
    current_riddle = bot_instance.get_current_riddle(chat_id)
    
    if not current_riddle:
        await update.message.reply_text("❌ No active game or riddle found! Start a new game first.")
        return
    
    bot_instance.game_data[chat_id]["hints_used"] += 1
    await update.message.reply_text(f"💡 **Hint:** {current_riddle['hint']}")

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show current game status."""
    bot_instance = context.bot_data.get('bot_instance')
    if not bot_instance:
        await update.message.reply_text("❌ Bot not properly initialized. Please restart.")
        return
    
    chat_id = update.message.chat_id
    session = bot_instance.game_data.get(chat_id)
    
    if not session:
        await update.message.reply_text("❌ No active game found! Start a new game first.")
        return
    
    current_riddle = bot_instance.get_current_riddle(chat_id)
    if not current_riddle:
        await update.message.reply_text("🏆 Game completed! Great job!")
        return
    
    progress = len(session["completed_riddles"])
    total = len(bot_instance.riddles)
    
    status_text = f"📊 **Game Status**\n\n"
    status_text += f"🎯 **Team:** {session['team_name']}\n"
    status_text += f"📈 **Progress:** {progress}/{total} riddles completed\n"
    status_text += f"💡 **Hints Used:** {session['hints_used']}\n"
    status_text += f"🧩 **Current Riddle:** #{current_riddle['id']}\n\n"
    status_text += f"**Current Challenge:**\n{current_riddle['riddle']}"
    
    await update.message.reply_text(status_text, parse_mode='Markdown')

def main():
    """Main function to run the bot."""
    import argparse
    import os
    
    # Set up argument parser
    parser = argparse.ArgumentParser(
        description="Telegram Treasure Hunt Bot - QR code-based treasure hunt game",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --token YOUR_BOT_TOKEN              # Run the bot
  %(prog)s --generate-qr                       # Generate QR codes only
  %(prog)s --generate-qr --output ./my_qr      # Generate QR codes to custom folder
  %(prog)s --token YOUR_TOKEN --validate       # Validate configuration
  %(prog)s --list-riddles                      # List all configured riddles
        """
    )
    
    # Add arguments
    parser.add_argument(
        '--token', '-t',
        type=str,
        default=os.environ.get('TELEGRAM_BOT_TOKEN'),
        help='Telegram bot token (can also use TELEGRAM_BOT_TOKEN environment variable)'
    )
    
    parser.add_argument(
        '--generate-qr', '-g',
        action='store_true',
        help='Generate QR code images for printing and exit'
    )
    
    parser.add_argument(
        '--output', '-o',
        type=str,
        default='qr_codes',
        help='Output directory for QR code images (default: qr_codes)'
    )
    
    parser.add_argument(
        '--list-riddles', '-l',
        action='store_true',
        help='List all configured riddles and exit'
    )
    
    parser.add_argument(
        '--validate', '-v',
        action='store_true',
        help='Validate configuration and exit'
    )
    
    parser.add_argument(
        '--debug',
        action='store_true',
        help='Enable debug logging'
    )
    
    # Parse arguments
    args = parser.parse_args()
    
    # Set up logging level
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
        print("🐛 Debug mode enabled")
    
    # Create bot instance for configuration validation
    bot_instance = TreasureHuntBot("dummy_token")
    
    # Handle list riddles command
    if args.list_riddles:
        print("📋 Configured Riddles:")
        print("=" * 50)
        for riddle in bot_instance.riddles:
            print(f"Stop {riddle['id']}: {riddle['location'].upper()}")
            print(f"Riddle: {riddle['riddle']}")
            print(f"Hint: {riddle['hint']}")
            print(f"QR Code: {riddle['qr_code']}")
            print("-" * 30)
        print(f"\n🎯 Total stops configured: {len(bot_instance.riddles)}")
        return
    
    # Handle QR code generation
    if args.generate_qr:
        print("🎯 Generating QR codes for treasure hunt...")
        success = bot_instance.save_qr_code_images(args.output)
        if success:
            print(f"\n✨ QR codes generated successfully in '{args.output}'!")
            print("📝 Next steps:")
            print("1. Print the QR code images on weatherproof paper/laminate them")
            print("2. Place them at the corresponding locations")
            print("3. Test each QR code with your phone before the event")
            print("4. Keep the summary file for reference during the event")
        return
    
    # Handle validation
    if args.validate:
        print("🔍 Validating configuration...")
        
        # Check riddles
        riddle_count = len(bot_instance.riddles)
        print(f"✅ Found {riddle_count} riddles configured")
        
        # Check for duplicate IDs
        ids = [r['id'] for r in bot_instance.riddles]
        if len(ids) != len(set(ids)):
            print("❌ Duplicate riddle IDs found!")
            return
        print("✅ All riddle IDs are unique")
        
        # Check for duplicate QR codes
        qr_codes = [r['qr_code'] for r in bot_instance.riddles]
        if len(qr_codes) != len(set(qr_codes)):
            print("❌ Duplicate QR codes found!")
            return
        print("✅ All QR codes are unique")
        
        # Check QR code format
        for riddle in bot_instance.riddles:
            if not riddle['qr_code'].startswith('TREASURE_HUNT_'):
                print(f"⚠️  QR code '{riddle['qr_code']}' doesn't follow recommended format")
        
        print("✅ Configuration validation passed!")
        return
    
    # For running the bot, token is required
    if not args.token:
        print("❌ Bot token required to run the bot!")
        print("💡 Options:")
        print("  1. Use --token YOUR_BOT_TOKEN")
        print("  2. Set TELEGRAM_BOT_TOKEN environment variable")
        print("  3. Use --generate-qr to generate QR codes without a token")
        parser.print_help()
        return
    
    # Create bot instance with real token
    bot_instance = TreasureHuntBot(args.token)
    
    # Create application
    application = Application.builder().token(args.token).build()
    
    # Store bot instance in bot_data for access in handlers
    application.bot_data['bot_instance'] = bot_instance
    
    # Add handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("hint", hint_command))
    application.add_handler(CommandHandler("status", status_command))
    application.add_handler(CallbackQueryHandler(button_callback))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # Start the bot
    print("🚀 Treasure Hunt Bot is starting...")
    print(f"🎯 Game configured with {len(bot_instance.riddles)} stops")
    print("📱 Bot is ready to receive messages!")
    print("🛑 Press Ctrl+C to stop the bot")
    
    try:
        application.run_polling(allowed_updates=Update.ALL_TYPES)
    except KeyboardInterrupt:
        print("\n👋 Bot stopped by user")
    except Exception as e:
        print(f"\n❌ Bot stopped due to error: {e}")
        if args.debug:
            import traceback
            traceback.print_exc()

if __name__ == '__main__':
    main()