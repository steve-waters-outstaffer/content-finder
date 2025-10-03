// src/components/intelligence/VOCDiscovery.jsx
import React, { useState } from 'react';
import { Loader2, AlertTriangle, Check } from 'lucide-react';
import VOCStepIndicator from './VOCStepIndicator';
import VOCStepContent from './VOCStepContent';

const STEPS = [
    { id: 'fetch-reddit', label: 'Fetch Reddit Posts', description: 'Gather posts from relevant subreddits' },
    { id: 'analyze-posts', label: 'Analyze Posts', description: 'AI scoring and filtering for relevance' },
    { id: 'fetch-trends', label: 'Fetch Google Trends', description: 'Get trending search data' },
    { id: 'generate-queries', label: 'Generate Queries', description: 'Create search queries from insights' }
];

export default function VOCDiscovery({ segment }) {
    const [currentStep, setCurrentStep] = useState(0);
    const [stepData, setStepData] = useState({
        'fetch-reddit': { status: 'pending', data: null, warnings: [] },
        'analyze-posts': { status: 'pending', data: null },
        'fetch-trends': { status: 'pending', data: null },
        'generate-queries': { status: 'pending', data: null }
    });
    const [isProcessing, setIsProcessing] = useState(false);

    const handleFetchReddit = async () => {
        setIsProcessing(true);
        setStepData(prev => ({
            ...prev,
            'fetch-reddit': { ...prev['fetch-reddit'], status: 'loading' }
        }));

        try {
            const response = await fetch(
                `${import.meta.env.VITE_API_URL}/api/intelligence/voc-discovery/fetch-reddit`,
                {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ segment_name: segment })
                }
            );

            const result = await response.json();

            setStepData(prev => ({
                ...prev,
                'fetch-reddit': {
                    status: 'completed',
                    data: result.posts || [],
                    warnings: result.warnings || [],
                    duration: result.duration_seconds
                }
            }));
        } catch (error) {
            setStepData(prev => ({
                ...prev,
                'fetch-reddit': { ...prev['fetch-reddit'], status: 'error', error: error.message }
            }));
        } finally {
            setIsProcessing(false);
        }
    };

    const handleAnalyzePosts = async () => {
        setIsProcessing(true);
        setStepData(prev => ({
            ...prev,
            'analyze-posts': { ...prev['analyze-posts'], status: 'loading' }
        }));

        try {
            // Call analyze endpoint with posts from previous step
            const response = await fetch(
                `${import.meta.env.VITE_API_URL}/api/intelligence/voc-discovery/analyze-posts`,
                {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        segment_name: segment,
                        posts: stepData['fetch-reddit'].data
                    })
                }
            );

            const result = await response.json();

            setStepData(prev => ({
                ...prev,
                'analyze-posts': {
                    status: 'completed',
                    data: result.analyzed_posts || [],
                    duration: result.duration_seconds
                }
            }));
        } catch (error) {
            setStepData(prev => ({
                ...prev,
                'analyze-posts': { ...prev['analyze-posts'], status: 'error', error: error.message }
            }));
        } finally {
            setIsProcessing(false);
        }
    };

    const canProceedToStep = (stepIndex) => {
        if (stepIndex === 0) return true;
        const prevStep = STEPS[stepIndex - 1];
        return stepData[prevStep.id].status === 'completed';
    };

    const currentStepId = STEPS[currentStep].id;
    const currentStepInfo = stepData[currentStepId];

    return (
        <div className="flex h-[calc(100vh-12rem)] bg-white rounded-lg shadow-sm border border-gray-200">
            {/* Left Sidebar - Step Indicator */}
            <div className="w-72 border-r border-gray-200 p-6 bg-gray-50">
                <VOCStepIndicator
                    steps={STEPS}
                    currentStep={currentStep}
                    stepData={stepData}
                    onStepClick={(index) => {
                        if (canProceedToStep(index)) {
                            setCurrentStep(index);
                        }
                    }}
                />
            </div>

            {/* Main Content Area */}
            <div className="flex-1 flex flex-col">
                <VOCStepContent
                    step={STEPS[currentStep]}
                    stepInfo={currentStepInfo}
                    isProcessing={isProcessing}
                    onExecute={() => {
                        switch (currentStepId) {
                            case 'fetch-reddit':
                                handleFetchReddit();
                                break;
                            case 'analyze-posts':
                                handleAnalyzePosts();
                                break;
                            // Add other cases
                        }
                    }}
                    onNext={() => {
                        if (currentStep < STEPS.length - 1) {
                            setCurrentStep(currentStep + 1);
                        }
                    }}
                    onPrevious={() => {
                        if (currentStep > 0) {
                            setCurrentStep(currentStep - 1);
                        }
                    }}
                    canProceed={currentStepInfo.status === 'completed'}
                    isLastStep={currentStep === STEPS.length - 1}
                />
            </div>
        </div>
    );
}