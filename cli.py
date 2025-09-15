#!/usr/bin/env python3
"""
CLI script for running the Content Finder Intelligence Engine
Usage: python cli.py [segment_name]
"""
import sys
import os
from pathlib import Path

# Add backend to Python path
backend_path = Path(__file__).parent / "backend"
sys.path.insert(0, str(backend_path))

try:
    from intelligence.intelligence_engine import IntelligenceEngine
except ImportError as e:
    print(f"Error importing intelligence engine: {e}")
    print("Make sure you're running from the project root directory")
    sys.exit(1)

def main():
    """Main CLI entry point"""
    try:
        # Change to backend directory for proper file paths
        os.chdir("backend")
        
        engine = IntelligenceEngine()
        
        if len(sys.argv) > 1:
            # Run specific segment
            segment_arg = sys.argv[1]
            
            # Convert segment name to key if needed
            if segment_arg in engine.config["segments"]:
                segment_key = segment_arg
            else:
                # Try to find by name
                segment_key = None
                for key, data in engine.config["segments"].items():
                    if data["name"].lower() == segment_arg.lower():
                        segment_key = key
                        break
                
                if not segment_key:
                    print(f"Error: Segment '{segment_arg}' not found")
                    print(f"Available segments:")
                    for key, data in engine.config["segments"].items():
                        print(f"  - {key} ({data['name']})")
                    return
            
            print(f"Running segment: {engine.config['segments'][segment_key]['name']}")
            results = engine.run_single_segment(segment_key)
            
            if 'error' in results:
                print(f"Error: {results['error']}")
            else:
                print(f"✅ Segment completed: {results['total_analyzed']} analyses generated")
        else:
            # Run all segments
            print("Running all intelligence segments...")
            results = engine.run_all_segments()
            
            print("\n📊 Final Summary:")
            total_analyzed = sum(s.get('total_analyzed', 0) for s in results.get('segments', {}).values())
            total_scraped = sum(s.get('total_scraped', 0) for s in results.get('segments', {}).values())
            print(f"  - Total content analyzed: {total_analyzed}")
            print(f"  - Total content scraped: {total_scraped}")
            print(f"  - Segments processed: {len(results.get('segments', {}))}")
            print(f"  - Output saved to: intelligence_output_{engine.run_id}/")
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
