"""
REST API for weather predictions.
Provides endpoints to query predictions from Kafka topics.
"""

import os
import sys
from datetime import datetime
from flask import Flask, jsonify, request
from flask_cors import CORS
from kafka import KafkaConsumer
import json

# Add src to path for imports
if os.path.exists('/app/src'):
    sys.path.insert(0, '/app/src')
else:
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    src_path = os.path.join(project_root, 'src')
    sys.path.insert(0, src_path)

from utils.config import KAFKA_BOOTSTRAP_SERVERS
from utils.kafka_config import (
    TOPIC_WEATHER_RAW,
    TOPIC_WEATHER_FEATURES,
    TOPIC_WEATHER_PREDICTIONS
)

app = Flask(__name__)
# Enable CORS for all routes
CORS(app, resources={r"/*": {"origins": "*"}})

@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint."""
    return jsonify({"status": "healthy", "service": "weather-api"}), 200

@app.route('/predictions/latest', methods=['GET'])
def get_latest_predictions():
    """Get latest predictions from Kafka."""
    try:
        from kafka import TopicPartition
        
        consumer = KafkaConsumer(
            bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
            auto_offset_reset='earliest',
            enable_auto_commit=False,
            consumer_timeout_ms=2000,
            value_deserializer=lambda m: json.loads(m.decode('utf-8'))
        )
        
        # Get all partitions for the topic
        partitions = consumer.partitions_for_topic(TOPIC_WEATHER_PREDICTIONS)
        if not partitions:
            consumer.close()
            return jsonify({"error": "Topic not found or no partitions available"}), 404
        
        # Create TopicPartition objects
        topic_partitions = [TopicPartition(TOPIC_WEATHER_PREDICTIONS, p) for p in partitions]
        consumer.assign(topic_partitions)
        
        # Get end offsets for all partitions
        end_offsets = consumer.end_offsets(topic_partitions)
        
        # Seek to end of each partition, then get the last message
        latest_messages = {}
        for tp in topic_partitions:
            end_offset = end_offsets.get(tp, 0)
            
            if end_offset > 0:
                # Seek to the last message (end_offset - 1)
                consumer.seek(tp, end_offset - 1)
                # Poll to get the message
                records = consumer.poll(timeout_ms=1000)
                for partition_records in records.values():
                    for message in partition_records:
                        if message.partition == tp.partition:
                            latest_messages[message.partition] = message.value
                            break
        
        consumer.close()
        
        if not latest_messages:
            return jsonify({"error": "No predictions available"}), 404
        
        return jsonify({
            "predictions": list(latest_messages.values()),
            "count": len(latest_messages)
        }), 200
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/predictions', methods=['GET'])
def get_predictions():
    """Get predictions with optional limit."""
    limit = request.args.get('limit', default=10, type=int)
    
    try:
        from kafka import TopicPartition
        
        consumer = KafkaConsumer(
            bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
            auto_offset_reset='latest',
            enable_auto_commit=False,
            consumer_timeout_ms=3000,
            value_deserializer=lambda m: json.loads(m.decode('utf-8'))
        )
        
        # Get all partitions for the topic
        partitions = consumer.partitions_for_topic(TOPIC_WEATHER_PREDICTIONS)
        if not partitions:
            consumer.close()
            return jsonify({"error": "Topic not found or no partitions available"}), 404
        
        # Create TopicPartition objects and assign
        topic_partitions = [TopicPartition(TOPIC_WEATHER_PREDICTIONS, p) for p in partitions]
        consumer.assign(topic_partitions)
        
        # Seek to beginning to read recent messages
        for tp in topic_partitions:
            # Get end offset
            consumer.seek_to_end(tp)
            end_offset = consumer.position(tp)
            # Seek to a position that gives us recent messages
            if end_offset > limit:
                consumer.seek(tp, max(0, end_offset - limit))
            else:
                consumer.seek_to_beginning(tp)
        
        # Poll for messages
        messages = []
        records = consumer.poll(timeout_ms=2000)
        for partition_records in records.values():
            for message in partition_records:
                messages.append(message.value)
                if len(messages) >= limit:
                    break
            if len(messages) >= limit:
                break
        
        # Sort by timestamp if available, most recent first
        messages.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
        messages = messages[:limit]
        
        consumer.close()
        
        return jsonify({
            "predictions": messages,
            "count": len(messages)
        }), 200
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/topics/weather-raw', methods=['GET'])
def get_weather_raw():
    """Get latest messages from weather-raw topic by partition."""
    return get_topic_messages(TOPIC_WEATHER_RAW)

@app.route('/topics/weather-features', methods=['GET'])
def get_weather_features():
    """Get latest messages from weather-features topic by partition."""
    return get_topic_messages(TOPIC_WEATHER_FEATURES)

@app.route('/topics/weather-predictions', methods=['GET'])
def get_weather_predictions_topic():
    """Get latest messages from weather-predictions topic by partition."""
    return get_topic_messages(TOPIC_WEATHER_PREDICTIONS)

def get_topic_messages(topic_name):
    """Helper function to get recent messages from a topic by partition."""
    try:
        from kafka import TopicPartition
        
        limit = request.args.get('limit', default=50, type=int)  # Get last 50 messages per partition
        
        consumer = KafkaConsumer(
            bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
            auto_offset_reset='latest',
            enable_auto_commit=False,
            consumer_timeout_ms=3000,
            value_deserializer=lambda m: json.loads(m.decode('utf-8'))
        )
        
        # Get all partitions for the topic
        partitions = consumer.partitions_for_topic(topic_name)
        if not partitions:
            consumer.close()
            return jsonify({"error": f"Topic {topic_name} not found or no partitions available"}), 404
        
        # Create TopicPartition objects
        topic_partitions = [TopicPartition(topic_name, p) for p in partitions]
        consumer.assign(topic_partitions)
        
        # Get end offsets for all partitions
        end_offsets = consumer.end_offsets(topic_partitions)
        
        # Get recent messages from each partition
        partition_data = {}
        for tp in topic_partitions:
            end_offset = end_offsets.get(tp, 0)
            
            if end_offset > 0:
                # Seek to get last N messages
                start_offset = max(0, end_offset - limit)
                consumer.seek(tp, start_offset)
                
                # Poll to get messages
                messages = []
                records = consumer.poll(timeout_ms=2000)
                for partition_records in records.values():
                    for message in partition_records:
                        if message.partition == tp.partition:
                            messages.append({
                                "offset": message.offset,
                                "timestamp": message.value.get('timestamp', ''),
                                "data": message.value
                            })
                
                # Sort by offset (ascending) so newest is last
                messages.sort(key=lambda x: x["offset"])
                partition_data[tp.partition] = messages
        
        consumer.close()
        
        return jsonify({
            "topic": topic_name,
            "partitions": partition_data,
            "count": sum(len(msgs) for msgs in partition_data.values())
        }), 200
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/stations/all', methods=['GET'])
def get_all_stations_data():
    """Get all data for all stations from all topics."""
    try:
        from kafka import TopicPartition
        
        result = {
            "stations": {},
            "timestamp": datetime.now().isoformat()
        }
        
        # Get data from all three topics
        topics = [
            (TOPIC_WEATHER_RAW, "raw"),
            (TOPIC_WEATHER_FEATURES, "features"),
            (TOPIC_WEATHER_PREDICTIONS, "predictions")
        ]
        
        for topic_name, data_type in topics:
            consumer = KafkaConsumer(
                bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
                auto_offset_reset='latest',
                enable_auto_commit=False,
                consumer_timeout_ms=2000,
                value_deserializer=lambda m: json.loads(m.decode('utf-8'))
            )
            
            partitions = consumer.partitions_for_topic(topic_name)
            if partitions:
                topic_partitions = [TopicPartition(topic_name, p) for p in partitions]
                consumer.assign(topic_partitions)
                
                # Get recent messages from each partition (last 10)
                end_offsets = consumer.end_offsets(topic_partitions)
                for tp in topic_partitions:
                    end_offset = end_offsets.get(tp, 0)
                    if end_offset > 0:
                        start_offset = max(0, end_offset - 10)
                        consumer.seek(tp, start_offset)
                
                records = consumer.poll(timeout_ms=2000)
                for partition_records in records.values():
                    for message in partition_records:
                        data = message.value
                        station_id = data.get('station_id', f'unknown_{message.partition}')
                        
                        if station_id not in result["stations"]:
                            result["stations"][station_id] = {
                                "station_id": station_id,
                                "station_name": data.get('station_name', station_id),
                                "raw": [],
                                "features": [],
                                "predictions": []
                            }
                        
                        result["stations"][station_id][data_type].append({
                            "partition": message.partition,
                            "offset": message.offset,
                            "timestamp": data.get('timestamp', ''),
                            "data": data
                        })
            
            consumer.close()
        
        # Sort each data type by timestamp (most recent first)
        for station_id in result["stations"]:
            for data_type in ["raw", "features", "predictions"]:
                result["stations"][station_id][data_type].sort(
                    key=lambda x: x.get("timestamp", ""), 
                    reverse=True
                )
        
        return jsonify(result), 200
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)

