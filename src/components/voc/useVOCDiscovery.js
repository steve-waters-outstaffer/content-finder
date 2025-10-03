import { useCallback, useEffect, useMemo, useState } from 'react';
import { API_BASE_URL, DEFAULT_SEGMENTS, STEPS } from './constants';

const createInitialStepData = () => ({
    'fetch-reddit': { status: 'pending', data: null, warnings: [], duration: null, unfilteredData: null, rawCount: 0 },
    'pre-score-posts': { status: 'pending', data: null, prescored: [], rejected: [], stats: null, threshold: null, duration: null },
    'enrich-posts': { status: 'pending', data: null, rejected: [], stats: null, threshold: null, duration: null },
    'fetch-trends': { status: 'pending', data: null, duration: null },
    'generate-queries': { status: 'pending', data: null, duration: null },
});

export const useVOCDiscovery = () => {
    const [segmentName, setSegmentName] = useState(DEFAULT_SEGMENTS[0]);
    const [availableSegments, setAvailableSegments] = useState(DEFAULT_SEGMENTS);
    const [error, setError] = useState('');
    const [stepData, setStepData] = useState(createInitialStepData);
    const [currentStep, setCurrentStep] = useState(0);
    const [isProcessing, setIsProcessing] = useState(false);
    const [segmentConfig, setSegmentConfig] = useState(null);

    // Load available segments on mount
    useEffect(() => {
        let isSubscribed = true;

        const loadSegments = async () => {
            try {
                const response = await fetch(`${API_BASE_URL}/api/intelligence/config`);
                if (!response.ok) {
                    return;
                }

                const config = await response.json();
                const segments =
                    config?.monthly_run?.segments?.map((segment) => segment.name).filter(Boolean) || [];

                if (isSubscribed && segments.length) {
                    setAvailableSegments(segments);
                    setSegmentName((prev) => (segments.includes(prev) ? prev : segments[0]));
                }
            } catch (configError) {
                console.warn('Unable to load intelligence segments:', configError);
            }
        };

        loadSegments();

        return () => {
            isSubscribed = false;
        };
    }, []);

    // Load segment config when segment changes
    useEffect(() => {
        setSegmentConfig(null);
        setCurrentStep(0);
        setStepData(createInitialStepData());
        setError('');

        if (!segmentName) {
            return;
        }

        let isCancelled = false;

        const fetchConfig = async () => {
            try {
                const response = await fetch(
                    `${API_BASE_URL}/api/segment-config/${encodeURIComponent(segmentName)}`,
                );

                if (!response.ok) {
                    throw new Error(`HTTP error! status: ${response.status}`);
                }

                const data = await response.json();
                if (!isCancelled) {
                    setSegmentConfig({
                        subreddits: Array.isArray(data.subreddits) ? data.subreddits : [],
                        trends_keywords: Array.isArray(data.trends_keywords) ? data.trends_keywords : [],
                    });
                }
            } catch (configError) {
                console.error('Failed to fetch segment config:', configError);
                if (!isCancelled) {
                    setSegmentConfig({ subreddits: [], trends_keywords: [] });
                }
            }
        };

        fetchConfig();

        return () => {
            isCancelled = true;
        };
    }, [segmentName]);

    const handleFetchReddit = useCallback(async () => {
        if (!segmentName) {
            return;
        }

        setIsProcessing(true);
        setError('');
        setStepData((prev) => ({
            ...prev,
            'fetch-reddit': { ...prev['fetch-reddit'], status: 'loading' },
        }));

        try {
            const response = await fetch(`${API_BASE_URL}/api/intelligence/voc-discovery/fetch-reddit`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ segment_name: segmentName }),
            });

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            const data = await response.json();
            setStepData((prev) => ({
                ...prev,
                'fetch-reddit': {
                    status: 'completed',
                    data: data.raw_posts || [],
                    unfilteredData: data.unfiltered_posts || [],
                    warnings: data.warnings || [],
                    duration: data.duration_ms ?? null,
                    rawCount: data.raw_count || 0,
                },
            }));
        } catch (fetchError) {
            console.error('Reddit fetch failed:', fetchError);
            setError('Failed to fetch Reddit posts. Please try again.');
            setStepData((prev) => ({
                ...prev,
                'fetch-reddit': { ...prev['fetch-reddit'], status: 'error', error: fetchError.message },
            }));
        } finally {
            setIsProcessing(false);
        }
    }, [segmentName]);

    const handlePreScorePosts = useCallback(async () => {
        setIsProcessing(true);
        setError('');
        setStepData((prev) => ({
            ...prev,
            'pre-score-posts': { ...prev['pre-score-posts'], status: 'loading' },
        }));

        try {
            const response = await fetch(`${API_BASE_URL}/api/intelligence/voc-discovery/pre-score-posts`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    segment_name: segmentName,
                    raw_posts: stepData['fetch-reddit'].data,
                }),
            });

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            const data = await response.json();
            setStepData((prev) => ({
                ...prev,
                'pre-score-posts': {
                    status: 'completed',
                    data: data.promising_posts || [],
                    prescored: data.prescored_posts || [],
                    rejected: data.rejected_posts || [],
                    stats: data.stats || null,
                    threshold: data.threshold ?? null,
                    duration: data.duration_ms ?? null,
                },
            }));
        } catch (preScoreError) {
            console.error('Pre-score failed:', preScoreError);
            setError('Failed to pre-score posts. Please try again.');
            setStepData((prev) => ({
                ...prev,
                'pre-score-posts': { ...prev['pre-score-posts'], status: 'error', error: preScoreError.message },
            }));
        } finally {
            setIsProcessing(false);
        }
    }, [segmentName, stepData]);

    const handleEnrichPosts = useCallback(async () => {
        setIsProcessing(true);
        setError('');
        setStepData((prev) => ({
            ...prev,
            'enrich-posts': { ...prev['enrich-posts'], status: 'loading' },
        }));

        try {
            const response = await fetch(`${API_BASE_URL}/api/intelligence/voc-discovery/enrich-posts`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    segment_name: segmentName,
                    promising_posts: stepData['pre-score-posts'].data,
                }),
            });

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            const data = await response.json();
            setStepData((prev) => ({
                ...prev,
                'enrich-posts': {
                    status: 'completed',
                    data: data.filtered_posts || [],
                    rejected: data.rejected_posts || [],
                    stats: data.stats || null,
                    threshold: data.threshold ?? null,
                    duration: data.duration_ms ?? null,
                },
            }));
        } catch (enrichError) {
            console.error('Enrichment failed:', enrichError);
            setError('Failed to enrich posts. Please try again.');
            setStepData((prev) => ({
                ...prev,
                'enrich-posts': { ...prev['enrich-posts'], status: 'error', error: enrichError.message },
            }));
        } finally {
            setIsProcessing(false);
        }
    }, [segmentName, stepData]);

    const handleFetchTrends = useCallback(async () => {
        setIsProcessing(true);
        setError('');
        setStepData((prev) => ({
            ...prev,
            'fetch-trends': { ...prev['fetch-trends'], status: 'loading' },
        }));

        try {
            const response = await fetch(`${API_BASE_URL}/api/intelligence/voc-discovery/fetch-trends`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ segment_name: segmentName }),
            });

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            const data = await response.json();
            setStepData((prev) => ({
                ...prev,
                'fetch-trends': {
                    status: 'completed',
                    data: data.trends || [],
                    duration: data.duration_ms ?? null,
                },
            }));
        } catch (trendsError) {
            console.error('Trends fetch failed:', trendsError);
            setError('Failed to fetch trends. Please try again.');
            setStepData((prev) => ({
                ...prev,
                'fetch-trends': { ...prev['fetch-trends'], status: 'error', error: trendsError.message },
            }));
        } finally {
            setIsProcessing(false);
        }
    }, [segmentName]);

    const handleGenerateQueries = useCallback(async () => {
        setIsProcessing(true);
        setError('');
        setStepData((prev) => ({
            ...prev,
            'generate-queries': { ...prev['generate-queries'], status: 'loading' },
        }));

        try {
            const response = await fetch(`${API_BASE_URL}/api/intelligence/voc-discovery/generate-queries`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    segment_name: segmentName,
                    filtered_posts: stepData['enrich-posts'].data,
                    trends: stepData['fetch-trends'].data,
                }),
            });

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            const data = await response.json();
            setStepData((prev) => ({
                ...prev,
                'generate-queries': {
                    status: 'completed',
                    data: data.queries || [],
                    duration: data.duration_ms ?? null,
                },
            }));
        } catch (queryError) {
            console.error('Query generation failed:', queryError);
            setError('Failed to generate queries. Please try again.');
            setStepData((prev) => ({
                ...prev,
                'generate-queries': { ...prev['generate-queries'], status: 'error', error: queryError.message },
            }));
        } finally {
            setIsProcessing(false);
        }
    }, [segmentName, stepData]);

    const handleExecuteStep = useCallback(() => {
        const currentStepId = STEPS[currentStep].id;
        switch (currentStepId) {
            case 'fetch-reddit':
                handleFetchReddit();
                break;
            case 'pre-score-posts':
                handlePreScorePosts();
                break;
            case 'enrich-posts':
                handleEnrichPosts();
                break;
            case 'fetch-trends':
                handleFetchTrends();
                break;
            case 'generate-queries':
                handleGenerateQueries();
                break;
            default:
                break;
        }
    }, [currentStep, handleEnrichPosts, handleFetchReddit, handleFetchTrends, handleGenerateQueries, handlePreScorePosts]);

    const canProceedToStep = useCallback(
        (stepIndex) => {
            if (stepIndex === 0) {
                return true;
            }
            const prevStep = STEPS[stepIndex - 1];
            return stepData[prevStep.id]?.status === 'completed';
        },
        [stepData],
    );

    const handleStepClick = useCallback(
        (stepIndex) => {
            if (canProceedToStep(stepIndex)) {
                setCurrentStep(stepIndex);
            }
        },
        [canProceedToStep],
    );

    const handleNext = useCallback(() => {
        setCurrentStep((prev) => (prev < STEPS.length - 1 ? prev + 1 : prev));
    }, []);

    const handlePrevious = useCallback(() => {
        setCurrentStep((prev) => (prev > 0 ? prev - 1 : prev));
    }, []);

    const handleReset = useCallback(() => {
        setCurrentStep(0);
        setStepData(createInitialStepData());
        setError('');
    }, []);

    const currentStepDef = useMemo(() => STEPS[currentStep], [currentStep]);
    const currentStepInfo = stepData[currentStepDef.id];

    return {
        availableSegments,
        canProceedToStep,
        currentStep,
        currentStepDef,
        currentStepInfo,
        error,
        handleExecuteStep,
        handleNext,
        handlePrevious,
        handleReset,
        handleStepClick,
        isProcessing,
        segmentConfig,
        segmentName,
        setSegmentName,
        stepData,
    };
};
