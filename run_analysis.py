"""
통합 분석 실행 스크립트
Integrated Analysis Runner
"""

import sys
import argparse
from datetime import datetime
from stock_surge_detector import KoreanStockSurgeDetector

try:
    from advanced_stock_predictor import AdvancedStockPredictor
    TENSORFLOW_AVAILABLE = True
except ImportError:
    TENSORFLOW_AVAILABLE = False
    print("⚠️ TensorFlow가 설치되지 않아 AI 분석 기능을 사용할 수 없습니다.")
    print("기본 분석만 실행됩니다.")

def run_basic_analysis():
    """기본 급등 탐지 분석 실행"""
    print("🔍 기본 급등 탐지 분석을 시작합니다...")
    detector = KoreanStockSurgeDetector()
    results = detector.run_analysis()
    return results

def run_advanced_analysis():
    """고급 AI 예측 분석 실행"""
    if not TENSORFLOW_AVAILABLE:
        print("❌ TensorFlow가 설치되지 않아 AI 분석을 실행할 수 없습니다.")
        print("pip install tensorflow 명령으로 설치 후 다시 시도해주세요.")
        return None
        
    print("🤖 AI 딥러닝 예측 분석을 시작합니다...")
    predictor = AdvancedStockPredictor()
    results = predictor.run_advanced_analysis()
    return results

def run_combined_analysis():
    """통합 분석 실행"""
    print("🚀 통합 주식 급등 분석 시스템")
    print("=" * 60)
    print(f"분석 시작 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    
    # 1. 기본 분석
    print("\n1️⃣ 기본 급등 탐지 분석")
    print("-" * 40)
    basic_results = run_basic_analysis()
    
    print("\n" + "="*60)
    input("Enter를 눌러 AI 분석을 계속하세요... (시간이 오래 걸릴 수 있습니다)")
    
    # 2. AI 분석
    print("\n2️⃣ AI 딥러닝 예측 분석")
    print("-" * 40)
    try:
        advanced_results = run_advanced_analysis()
    except Exception as e:
        print(f"AI 분석 중 오류 발생: {e}")
        print("기본 분석 결과만 제공됩니다.")
        advanced_results = None
    
    # 3. 결과 비교 및 종합
    print("\n3️⃣ 종합 분석 결과")
    print("=" * 60)
    
    if basic_results and advanced_results:
        print("📊 기본 분석과 AI 분석 결과를 종합합니다...")
        
        # 기본 분석 상위 3개
        basic_top3 = sorted(basic_results, key=lambda x: x['surge_score'], reverse=True)[:3]
        print("\n🔍 기본 분석 TOP 3:")
        for i, result in enumerate(basic_top3, 1):
            print(f"  {i}. {result['symbol']} (점수: {result['surge_score']})")
        
        # AI 분석 상위 3개
        ai_top3 = advanced_results[:3]
        print("\n🤖 AI 분석 TOP 3:")
        for i, result in enumerate(ai_top3, 1):
            print(f"  {i}. {result['name']} (확률: {result['surge_probability']:.1f}%)")
        
        # 공통 종목 찾기
        basic_symbols = {result['symbol'] for result in basic_top3}
        ai_symbols = {result['symbol'] for result in ai_top3}
        common_symbols = basic_symbols.intersection(ai_symbols)
        
        if common_symbols:
            print(f"\n🎯 두 분석에서 공통으로 선정된 종목: {', '.join(common_symbols)}")
            print("   → 이 종목들은 특히 주목할 가치가 있습니다!")
        else:
            print("\n📝 두 분석 결과가 다릅니다. 다양한 관점에서 검토해보세요.")
    
    elif basic_results:
        print("✅ 기본 분석 결과만 제공됩니다.")
        basic_top3 = sorted(basic_results, key=lambda x: x['surge_score'], reverse=True)[:3]
        print("\n🔍 기본 분석 추천 종목:")
        for i, result in enumerate(basic_top3, 1):
            print(f"  {i}. {result['symbol']} (점수: {result['surge_score']})")
    
    else:
        print("❌ 분석 결과를 가져올 수 없습니다.")
    
    print("\n" + "=" * 60)
    print("📝 분석 완료!")
    print(f"완료 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    
    print("\n⚠️  투자 유의사항:")
    print("• 이 분석은 참고용이며, 실제 투자 결과를 보장하지 않습니다.")
    print("• 주식 투자는 원금 손실 위험이 있으니 신중하게 결정하시기 바랍니다.")
    print("• 다양한 정보를 종합하여 투자 결정을 내리시기 바랍니다.")

def main():
    """메인 함수"""
    parser = argparse.ArgumentParser(description='한국 주식 급등 예측 분석')
    parser.add_argument(
        '--mode', 
        choices=['basic', 'advanced', 'combined'], 
        default='combined',
        help='분석 모드 선택 (basic: 기본분석, advanced: AI분석, combined: 통합분석)'
    )
    
    args = parser.parse_args()
    
    try:
        if args.mode == 'basic':
            run_basic_analysis()
        elif args.mode == 'advanced':
            run_advanced_analysis()
        else:  # combined
            run_combined_analysis()
            
    except KeyboardInterrupt:
        print("\n\n분석이 사용자에 의해 중단되었습니다.")
        sys.exit(0)
    except Exception as e:
        print(f"\n오류가 발생했습니다: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()