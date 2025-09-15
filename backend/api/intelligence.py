"""Intelligence Engine API endpoints"""
import os
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from flask import Blueprint, request, jsonify

# Import the intelligence engine directly
from intelligence.intelligence_engine import IntelligenceEngine

intelligence_bp = Blueprint('intelligence', __name__)

def log_run_event(event_type, data):
    """Log intelligence run events to JSON file"""
    log_file = Path('intelligence_run_logs.json')
    
    # Load existing logs
    logs = []
    if log_file.exists():
        try:
            with open(log_file, 'r', encoding='utf-8') as f:
                logs = json.load(f)
        except:
            logs = []
    
    # Add new log entry
    log_entry = {
        'timestamp': datetime.now().isoformat(),
        'event_type': event_type,
        'data': data
    }
    logs.append(log_entry)
    
    # Save logs
    with open(log_file, 'w', encoding='utf-8') as f:
        json.dump(logs, f, indent=2)
    
    print(f"📝 Logged: {event_type} - {data}")
    return log_entry

@intelligence_bp.route('/intelligence/config', methods=['GET'])
def get_intelligence_config():
    """Get the intelligence configuration"""
    try:
        config_path = "intelligence/config/intelligence_config.json"
        
        if not Path(config_path).exists():
            return jsonify({'error': 'Configuration file not found'}), 404
        
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        # Transform config for frontend compatibility
        transformed_config = {
            'monthly_run': {
                'scrape_top': config.get('defaults', {}).get('scrape_limit', 3),
                'segments': []
            }
        }
        
        # Transform segments
        for segment_key, segment_data in config.get('segments', {}).items():
            transformed_segment = {
                'name': segment_data['name'],
                'prompt_file': segment_data['prompt_file'],
                'enhanced_searches': segment_data.get('searches', [])
            }
            transformed_config['monthly_run']['segments'].append(transformed_segment)
        
        return jsonify(transformed_config)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@intelligence_bp.route('/intelligence/process-segment', methods=['POST'])
def process_single_segment():
    """Process a single segment"""
    try:
        data = request.get_json()
        segment_name = data.get('segment_name')
        
        if not segment_name:
            return jsonify({'error': 'segment_name is required'}), 400
        
        # Convert segment name to key format
        segment_key = segment_name.lower().replace(' ', '_')
        
        # Log segment start
        run_id = datetime.now().strftime("%Y_%m_%d_%H%M")
        log_run_event('segment_started', {
            'run_id': run_id,
            'segment_name': segment_name,
            'segment_key': segment_key,
            'trigger': 'api_request'
        })
        
        # Initialize and run intelligence engine
        engine = IntelligenceEngine()
        
        # Check if segment exists
        if segment_key not in engine.config.get('segments', {}):
            available_segments = list(engine.config.get('segments', {}).keys())
            log_run_event('segment_failed', {
                'run_id': run_id,
                'segment_key': segment_key,
                'error': f'Segment not found. Available: {available_segments}'
            })
            return jsonify({
                'error': f'Segment "{segment_name}" not found',
                'available_segments': [engine.config['segments'][k]['name'] for k in available_segments]
            }), 400
        
        # Run the segment
        result = engine.run_single_segment(segment_key)
        
        # Check if processing was successful
        if 'error' in result:
            log_run_event('segment_failed', {
                'run_id': run_id,
                'segment_key': segment_key,
                'error': result['error']
            })
            return jsonify({
                'error': f'Segment processing failed: {result["error"]}'
            }), 500
        
        # Transform result for frontend
        search_results = result.get('search_results', [])
        successful_searches = len([r for r in search_results if r.get('status') == 'success'])
        total_searches = len(search_results)
        
        response_data = {
            'segment_name': segment_name,
            'segment_key': segment_key,
            'searches_total': total_searches,
            'searches_successful': successful_searches,
            'total_scraped': result.get('total_scraped', 0),
            'total_analyzed': result.get('total_analyzed', 0),
            'status': 'success',
            'run_id': run_id,
            'started_at': result.get('started_at'),
            'completed_at': result.get('completed_at')
        }
        
        log_run_event('segment_completed', {
            'run_id': run_id,
            'segment_key': segment_key,
            'result_summary': response_data
        })
        
        return jsonify(response_data)
        
    except Exception as e:
        log_run_event('segment_error', {
            'run_id': run_id if 'run_id' in locals() else 'unknown',
            'segment_name': segment_name if 'segment_name' in locals() else 'unknown',
            'exception': str(e)
        })
        return jsonify({'error': str(e)}), 500

@intelligence_bp.route('/intelligence/run-all', methods=['POST'])
def run_all_segments():
    """Run all intelligence segments"""
    try:
        # Log run start
        run_id = datetime.now().strftime("%Y_%m_%d_%H%M")
        log_run_event('full_run_started', {
            'run_id': run_id,
            'trigger': 'api_request'
        })
        
        # Initialize and run intelligence engine
        engine = IntelligenceEngine()
        result = engine.run_all_segments()
        
        # Transform result for response
        segments_summary = {}
        total_analyzed = 0
        total_scraped = 0
        total_searches = 0
        
        for segment_key, segment_data in result.get('segments', {}).items():
            if 'error' not in segment_data:
                search_results = segment_data.get('search_results', [])
                successful_searches = len([r for r in search_results if r.get('status') == 'success'])
                
                segments_summary[segment_key] = {
                    'name': segment_data.get('segment_name', segment_key),
                    'searches_total': len(search_results),
                    'searches_successful': successful_searches,
                    'total_scraped': segment_data.get('total_scraped', 0),
                    'total_analyzed': segment_data.get('total_analyzed', 0),
                    'status': 'success'
                }
                
                total_analyzed += segment_data.get('total_analyzed', 0)
                total_scraped += segment_data.get('total_scraped', 0)
                total_searches += len(search_results)
            else:
                segments_summary[segment_key] = {
                    'name': segment_key,
                    'status': 'failed',
                    'error': segment_data['error']
                }
        
        response_data = {
            'run_id': result.get('run_id', run_id),
            'started_at': result.get('started_at'),
            'completed_at': result.get('completed_at'),
            'status': 'success',
            'segments': segments_summary,
            'summary': {
                'total_segments': len(segments_summary),
                'total_searches': total_searches,
                'total_scraped': total_scraped,
                'total_analyzed': total_analyzed
            }
        }
        
        log_run_event('full_run_completed', {
            'run_id': run_id,
            'summary': response_data['summary']
        })
        
        return jsonify(response_data)
        
    except Exception as e:
        log_run_event('full_run_error', {
            'run_id': run_id if 'run_id' in locals() else 'unknown',
            'exception': str(e)
        })
        return jsonify({'error': str(e)}), 500

@intelligence_bp.route('/intelligence/logs', methods=['GET'])
def get_intelligence_logs():
    """Get intelligence run logs"""
    try:
        log_file = Path('intelligence_run_logs.json')
        if not log_file.exists():
            return jsonify({'logs': []})
        
        with open(log_file, 'r', encoding='utf-8') as f:
            logs = json.load(f)
        
        # Get latest 50 logs, newest first
        logs = sorted(logs, key=lambda x: x['timestamp'], reverse=True)[:50]
        
        return jsonify({'logs': logs})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@intelligence_bp.route('/intelligence/results', methods=['GET'])
def get_intelligence_results():
    """Get list of available intelligence run results"""
    try:
        base_dir = Path('.')
        runs = []
        
        # Look for intelligence_output_* directories
        for dir_path in base_dir.glob('intelligence_output_*'):
            if dir_path.is_dir():
                run_id = dir_path.name.replace('intelligence_output_', '')
                
                # Check for run summary
                summary_file = dir_path / 'run_summary.json'
                if summary_file.exists():
                    try:
                        with open(summary_file, 'r', encoding='utf-8') as f:
                            summary = json.load(f)
                        
                        runs.append({
                            'run_id': run_id,
                            'started_at': summary.get('started_at'),
                            'completed_at': summary.get('completed_at'),
                            'segments': list(summary.get('segments', {}).keys()),
                            'status': 'completed'
                        })
                    except Exception as e:
                        print(f"Error reading summary for {run_id}: {e}")
                        runs.append({
                            'run_id': run_id,
                            'status': 'unknown',
                            'error': str(e)
                        })
        
        # Sort by run_id (timestamp), newest first
        runs.sort(key=lambda x: x['run_id'], reverse=True)
        
        return jsonify({'runs': runs})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@intelligence_bp.route('/intelligence/results/<run_id>', methods=['GET'])
def get_run_details(run_id):
    """Get detailed results for a specific run"""
    try:
        results_dir = Path(f'intelligence_output_{run_id}')
        if not results_dir.exists():
            return jsonify({'error': f'Run {run_id} not found'}), 404
        
        summary_file = results_dir / 'run_summary.json'
        if not summary_file.exists():
            return jsonify({'error': f'Summary file not found for run {run_id}'}), 404
        
        with open(summary_file, 'r', encoding='utf-8') as f:
            summary = json.load(f)
        
        return jsonify(summary)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@intelligence_bp.route('/intelligence/results/<run_id>/<segment_key>', methods=['GET'])
def get_segment_results(run_id, segment_key):
    """Get detailed results for a specific segment in a run"""
    try:
        segment_dir = Path(f'intelligence_output_{run_id}') / segment_key
        if not segment_dir.exists():
            return jsonify({'error': f'Segment {segment_key} not found in run {run_id}'}), 404
        
        # Look for segment results file
        results_file = segment_dir / f'{segment_key}_results_{run_id}.json'
        if not results_file.exists():
            return jsonify({'error': f'Results file not found for segment {segment_key}'}), 404
        
        with open(results_file, 'r', encoding='utf-8') as f:
            results = json.load(f)
        
        return jsonify(results)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@intelligence_bp.route('/segments', methods=['GET'])
def get_segments():
    try:
        segments = engine.get_segments()
        segment_names = [s.get("name") for s in segments]
        return jsonify(segment_names)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@intelligence_bp.route('/start-research', methods=['POST'])
def start_research():
    data = request.get_json()
    segment_name = data.get('segment')
    if not segment_name:
        return jsonify({"error": "Segment name is required."}), 400
    try:
        results = engine.start_research_phase(segment_name)
        return jsonify(results)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@intelligence_bp.route('/start-processing', methods=['POST'])
def start_processing():
    data = request.get_json()
    segment_name = data.get('segment')
    urls = data.get('urls')
    if not segment_name or not urls:
        return jsonify({"error": "Segment name and a list of URLs are required."}), 400
    try:
        engine.start_processing_phase(segment_name, urls)
        return jsonify({"message": f"Processing started for {len(urls)} URLs."})
    except Exception as e:
        return jsonify({"error": str(e)}), 500