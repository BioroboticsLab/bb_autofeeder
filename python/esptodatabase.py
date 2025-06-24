import serial
import sqlite3
import time
import re
import logging
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    filename='pump_monitor.log',
    filemode='a'
)

# Serial port configuration
SERIAL_PORT = '/dev/ttyUSB0'
BAUD_RATE = 115200

# Database configuration
DATABASE = "res.db"

# Constants
MIN_PUMP_INTERVAL = 0.4 # Such that we will not count double, in case serial message gets send again.
MAX_REASONABLE_PUMPS = 3
ESP_RESET_THRESHOLD = 10 

def connect_db():
    """Connect to the SQLite database."""
    try:
        conn = sqlite3.connect(DATABASE)
        return conn
    except sqlite3.Error as e:
        logging.error(f"Database connection error: {e}")
        return None

def initialize_db():
    """Create the database and table if they don't exist."""
    conn = connect_db()
    if conn:
        try:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS pumplog (
                    ID INTEGER PRIMARY KEY AUTOINCREMENT,
                    Timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    pump_id TEXT
                )
            """)
            conn.commit()
            logging.info("Database initialized successfully")
        except sqlite3.Error as e:
            logging.error(f"Database initialization error: {e}")
        finally:
            conn.close()

def add_pump_log_entry(pump_id):
    """Add a pump log entry to the database."""
    conn = connect_db()
    if conn:
        try:
            cursor = conn.cursor()
            cursor.execute("INSERT INTO pumplog (pump_id) VALUES (?)", (pump_id,))
            conn.commit()
            logging.info(f"Added pump log entry: {pump_id}")
        except sqlite3.Error as e:
            logging.error(f"Error adding pump log entry: {e}")
        finally:
            conn.close()

def monitor_serial():
    """Monitor the serial port for pump activations."""
    # Initialize the database
    initialize_db()
    
    # Keep track of the last seen pump count
    last_pump_count = 0
    
    # Keep track of the last time a pump was detected
    last_pump_time = time.time()
    
    # Flag to indicate if we've seen a valid pump count yet
    first_reading = True
    
    # Track consecutive identical readings to confirm stability
    consecutive_identical_readings = 0
    
    # Track the highest pump count seen
    highest_pump_count = 0
    
    try:
        # Open serial connection
        ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)
        logging.info(f"Connected to {SERIAL_PORT} at {BAUD_RATE} baud")
        
        # Regular expression to extract pump count - more specific pattern
        pump_count_pattern = re.compile(r"^Pumps since power up: (\d+)$")
        
        # Buffer for incomplete lines
        buffer = ""
        
        # Set to keep track of processed timestamps to avoid duplicates
        # Use timestamps instead of line content to better handle ESP resets
        processed_timestamps = set()
        
        while True:
            # Read data from serial port
            if ser.in_waiting:
                try:
                    data = ser.read(ser.in_waiting).decode('utf-8', errors='replace')
                    buffer += data
                    
                    # Process complete lines
                    lines = buffer.split('\n')
                    buffer = lines.pop()  # Keep the last incomplete line in the buffer
                    
                    for line in lines:
                        line = line.strip()
                        
                        # Skip empty lines
                        if not line:
                            continue
                        
                        logging.debug(f"Serial data: {line}")
                        
                        # Check for pump count
                        match = pump_count_pattern.search(line)
                        if match:
                            try:
                                current_pump_count = int(match.group(1))
                                current_time = time.time()
                                
                                # Update highest pump count seen
                                highest_pump_count = max(highest_pump_count, current_pump_count)
                                
                                # Check for ESP reset (pump count suddenly drops)
                                if not first_reading and current_pump_count < last_pump_count:
                                    # if last_pump_count - current_pump_count > ESP_RESET_THRESHOLD:
                                    logging.warning(f"Detected possible ESP reset: pump count dropped from {last_pump_count} to {current_pump_count}")
                                    # After reset, we should consider the current count as the new baseline
                                    last_pump_count = 0
                                    highest_pump_count = current_pump_count
                                
                                # If this is the first reading, just store it and wait for the next one
                                if first_reading:
                                    logging.info(f"Initial pump count: {current_pump_count}")
                                    last_pump_count = current_pump_count
                                    first_reading = False
                                    continue
                                
                                # Check if count has increased
                                if current_pump_count > last_pump_count:
                                    # Calculate new pumps
                                    new_pumps = current_pump_count - last_pump_count
                                    
                                    # Sanity check: is this a reasonable number of pumps?
                                    if new_pumps > MAX_REASONABLE_PUMPS:
                                        logging.warning(f"Unusually high pump count detected: {new_pumps}. Limiting to {MAX_REASONABLE_PUMPS}.")
                                        # new_pumps = MAX_REASONABLE_PUMPS
                                    
                                    # Check if enough time has passed since the last pump
                                    # We do this, in case serial message gets repeated
                                    time_since_last_pump = current_time - last_pump_time
                                    
                                    # Create a timestamp key for this detection (round to nearest second)
                                    detection_key = int(current_time)
                                    
                                    # Only process if we haven't seen this timestamp or if enough time has passed
                                    if detection_key not in processed_timestamps and time_since_last_pump >= MIN_PUMP_INTERVAL:
                                        logging.info(f"Detected {new_pumps} new pump activations (count: {current_pump_count}, previous: {last_pump_count})")
                                        
                                        # Add to processed timestamps
                                        processed_timestamps.add(detection_key)
                                        # Keep set size reasonable
                                        if len(processed_timestamps) > 100:
                                            processed_timestamps = set(sorted(list(processed_timestamps))[-100:])
                                        
                                        # Add entries for each new pump
                                        for i in range(new_pumps):
                                            add_pump_log_entry(f"ESP32_Pump")
                                        
                                        # Update last pump time
                                        last_pump_time = current_time
                                    elif detection_key in processed_timestamps:
                                        logging.debug(f"Skipping duplicate timestamp: {detection_key}")
                                    elif time_since_last_pump < MIN_PUMP_INTERVAL:
                                        logging.debug(f"Skipping - too soon after previous detection ({time_since_last_pump:.2f}s)")
                                
                                # Update last pump count
                                last_pump_count = current_pump_count
                                
                            except ValueError as e:
                                logging.error(f"Error parsing pump count: {e}")
                except UnicodeDecodeError as e:
                    logging.error(f"Unicode decode error: {e}")
                    buffer = ""  # Clear buffer on decode error
            
            # Small delay to prevent CPU hogging
            time.sleep(0.1)
    
    except serial.SerialException as e:
        logging.error(f"Serial port error: {e}")
    except KeyboardInterrupt:
        logging.info("Monitoring stopped by user")
    finally:
        if 'ser' in locals() and ser.is_open:
            ser.close()
            logging.info("Serial connection closed")

if __name__ == "__main__":
    print("Starting pump monitoring...")
    print("Press Ctrl+C to stop")
    monitor_serial()
