// src/components/intelligence/VOCDiscovery.jsx
import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
    Alert,
    Box,
    Button,
    Card,
    CardContent,
    Chip,
    CircularProgress,
    Divider,
    Grid,
    Stack,
    TextField,
    Typography,
    MenuItem,
    Paper,
    Link,
    List,
    ListItem,
    ListItemIcon,
    ListItemText,
    ListItemButton,
} from '@mui/material';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import RadioButtonUncheckedIcon from '@mui/icons-material/RadioButtonUnchecked';
import ForumIcon from '@mui/icons-material/Forum';
import TrendingUpIcon from '@mui/icons-material/TrendingUp';
import AutoAwesomeIcon from '@mui/icons-material/AutoAwesome';
import InsightsIcon from '@mui/icons-material/Insights';
import WarningIcon from '@mui/icons-material/Warning';
import ChevronRightIcon from '@mui/icons-material/ChevronRight';
import ChevronLeftIcon from '@mui/icons-material/ChevronLeft';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import { 
    Accordion,
    AccordionSummary,
    AccordionDetails,
    Table,
    TableBody,
    TableCell,
    TableContainer,
    TableHead,
    TableRow,
} from '@mui/material';
import { CustomColors, FontWeight } from '../../theme';

const DEFAULT_API_BASE = 'https://content-finder-backend-4ajpjhwlsq-ts.a.run.app';
const API_BASE_URL = import.meta.env.VITE_BACKEND_URL || DEFAULT_API_BASE;

const defaultSegments = ['SMB Leaders'];

const STEPS = [
    { 
        id: 'fetch-reddit', 
        label: 'Fetch Reddit Posts', 
        description: 'Gather posts from relevant subreddits',
        icon: ForumIcon,
    },
    { 
        id: 'pre-score-posts', 
        label: 'Pre-Score Posts', 
        description: 'Fast AI batch scoring (title + snippet only)',
        icon: AutoAwesomeIcon,
    },
    { 
        id: 'enrich-posts', 
        label: 'Enrich High-Scorers', 
        description: 'Fetch comments + deep AI analysis',
        icon: InsightsIcon,
    },
    { 
        id: 'fetch-trends', 
        label: 'Fetch Google Trends', 
        description: 'Get trending search data',
        icon: TrendingUpIcon,
    },
    { 
        id: 'generate-queries', 
        label: 'Generate Queries', 
        description: 'Create search queries from insights',
        icon: InsightsIcon,
    },
];

const PostCard = ({ post, showAnalysis }) => (
    <Card variant="outlined" sx={{ mb: 2 }}>
        <CardContent sx={{ p: 2 }}>
            <Typography variant="subtitle1" fontWeight={FontWeight.Medium}>
                {post.title}
            </Typography>
            <Typography variant="caption" color="text.secondary">
                r/{post.subreddit} • Score {post.score} • {post.num_comments} comments
            </Typography>
            {post.content_snippet && (
                <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
                    {post.content_snippet}
                </Typography>
            )}
            {showAnalysis && post.ai_analysis && (
                <Box sx={{ mt: 2, p: 2, bgcolor: CustomColors.UIGrey100, borderRadius: 1 }}>
                    <Typography variant="subtitle2" fontWeight={FontWeight.SemiBold} gutterBottom>
                        AI Insight
                    </Typography>
                    <Typography variant="body2">
                        <strong>Relevance:</strong> {post.ai_analysis.relevance_score ?? 'n/a'}
                    </Typography>
                    {post.ai_analysis.identified_pain_point && (
                        <Typography variant="body2" sx={{ mt: 0.5 }}>
                            <strong>Pain Point:</strong> {post.ai_analysis.identified_pain_point}
                        </Typography>
                    )}
                    {post.ai_analysis.reasoning && (
                        <Typography variant="body2" sx={{ mt: 0.5 }} color="text.secondary">
                            {post.ai_analysis.reasoning}
                        </Typography>
                    )}
                </Box>
            )}
            {post.url && (
                <Typography variant="body2" sx={{ mt: 1 }}>
                    <Link href={post.url} target="_blank" rel="noreferrer">
                        View discussion
                    </Link>
                </Typography>
            )}
        </CardContent>
    </Card>
);

const VOCDiscovery = () => {
    const [segmentName, setSegmentName] = useState(defaultSegments[0]);
    const [availableSegments, setAvailableSegments] = useState(defaultSegments);
    const [error, setError] = useState('');
    const [warnings, setWarnings] = useState([]);
    
    const [stepData, setStepData] = useState({
        'fetch-reddit': { status: 'pending', data: null, warnings: [], duration: null },
        'pre-score-posts': { status: 'pending', data: null, duration: null },
        'enrich-posts': { status: 'pending', data: null, duration: null },
        'fetch-trends': { status: 'pending', data: null, duration: null },
        'generate-queries': { status: 'pending', data: null, duration: null },
    });
    
    const [currentStep, setCurrentStep] = useState(0);
    const [isProcessing, setIsProcessing] = useState(false);
    const [segmentConfig, setSegmentConfig] = useState(null);

    // Load available segments on mount
    useEffect(() => {
        const loadSegments = async () => {
            try {
                const response = await fetch(`${API_BASE_URL}/api/intelligence/config`);
                if (!response.ok) return;
                
                const config = await response.json();
                const segments = config?.monthly_run?.segments?.map((segment) => segment.name).filter(Boolean) || [];

                if (segments.length) {
                    setAvailableSegments(segments);
                    if (!segments.includes(segmentName)) {
                        setSegmentName(segments[0]);
                    }
                }
            } catch (configError) {
                console.warn('Unable to load intelligence segments:', configError);
            }
        };

        loadSegments();
    }, []);

    // Load segment config when segment changes
    useEffect(() => {
        setSegmentConfig(null);
        setCurrentStep(0);
        setStepData({
            'fetch-reddit': { status: 'pending', data: null, warnings: [], duration: null },
            'analyze-posts': { status: 'pending', data: null, duration: null },
            'fetch-trends': { status: 'pending', data: null, duration: null },
            'generate-queries': { status: 'pending', data: null, duration: null },
        });
        setWarnings([]);
        setError('');

        if (!segmentName) return;

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

    // Stage 1: Fetch Reddit Posts
    const handleFetchReddit = async () => {
        if (!segmentName) return;

        setIsProcessing(true);
        setError('');
        setStepData(prev => ({
            ...prev,
            'fetch-reddit': { ...prev['fetch-reddit'], status: 'loading' }
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
            setStepData(prev => ({
                ...prev,
                'fetch-reddit': {
                    status: 'completed',
                    data: data.raw_posts || [],
                    unfilteredData: data.unfiltered_posts || [],  // NEW: Store truly raw data
                    warnings: data.warnings || [],
                    duration: data.duration_ms,
                    rawCount: data.raw_count || 0
                }
            }));
        } catch (err) {
            console.error('Reddit fetch failed:', err);
            setError('Failed to fetch Reddit posts. Please try again.');
            setStepData(prev => ({
                ...prev,
                'fetch-reddit': { ...prev['fetch-reddit'], status: 'error', error: err.message }
            }));
        } finally {
            setIsProcessing(false);
        }
    };

    // Stage 2: Pre-Score Posts
    const handlePreScorePosts = async () => {
        setIsProcessing(true);
        setError('');
        setStepData(prev => ({
            ...prev,
            'pre-score-posts': { ...prev['pre-score-posts'], status: 'loading' }
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
            setStepData(prev => ({
                ...prev,
                'pre-score-posts': {
                    status: 'completed',
                    data: data.promising_posts || [],
                    prescored: data.prescored_posts || [],
                    rejected: data.rejected_posts || [],
                    stats: data.stats,
                    threshold: data.threshold,
                    duration: data.duration_ms
                }
            }));
        } catch (err) {
            console.error('Pre-score failed:', err);
            setError('Failed to pre-score posts. Please try again.');
            setStepData(prev => ({
                ...prev,
                'pre-score-posts': { ...prev['pre-score-posts'], status: 'error', error: err.message }
            }));
        } finally {
            setIsProcessing(false);
        }
    };

    // Stage 3: Enrich High-Scoring Posts
    const handleEnrichPosts = async () => {
        setIsProcessing(true);
        setError('');
        setStepData(prev => ({
            ...prev,
            'enrich-posts': { ...prev['enrich-posts'], status: 'loading' }
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
            setStepData(prev => ({
                ...prev,
                'enrich-posts': {
                    status: 'completed',
                    data: data.filtered_posts || [],
                    rejected: data.rejected_posts || [],
                    stats: data.stats,
                    threshold: data.threshold,
                    duration: data.duration_ms
                }
            }));
        } catch (err) {
            console.error('Enrichment failed:', err);
            setError('Failed to enrich posts. Please try again.');
            setStepData(prev => ({
                ...prev,
                'enrich-posts': { ...prev['enrich-posts'], status: 'error', error: err.message }
            }));
        } finally {
            setIsProcessing(false);
        }
    };

    // Stage 2: Analyze Posts (DEPRECATED)
    const handleAnalyzePosts = async () => {
        setIsProcessing(true);
        setError('');
        setStepData(prev => ({
            ...prev,
            'analyze-posts': { ...prev['analyze-posts'], status: 'loading' }
        }));

        try {
            const response = await fetch(`${API_BASE_URL}/api/intelligence/voc-discovery/analyze-posts`, {
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
            setStepData(prev => ({
                ...prev,
                'analyze-posts': {
                    status: 'completed',
                    data: data.filtered_posts || [],
                    rejectedData: data.rejected_posts || [],
                    duration: data.duration_ms
                }
            }));
        } catch (err) {
            console.error('Post analysis failed:', err);
            setError('Failed to analyze posts. Please try again.');
            setStepData(prev => ({
                ...prev,
                'analyze-posts': { ...prev['analyze-posts'], status: 'error', error: err.message }
            }));
        } finally {
            setIsProcessing(false);
        }
    };

    // Stage 3: Fetch Trends
    const handleFetchTrends = async () => {
        setIsProcessing(true);
        setError('');
        setStepData(prev => ({
            ...prev,
            'fetch-trends': { ...prev['fetch-trends'], status: 'loading' }
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
            setStepData(prev => ({
                ...prev,
                'fetch-trends': {
                    status: 'completed',
                    data: data.trends || [],
                    duration: data.duration_ms
                }
            }));
        } catch (err) {
            console.error('Trends fetch failed:', err);
            setError('Failed to fetch trends. Please try again.');
            setStepData(prev => ({
                ...prev,
                'fetch-trends': { ...prev['fetch-trends'], status: 'error', error: err.message }
            }));
        } finally {
            setIsProcessing(false);
        }
    };

    // Stage 4: Generate Queries
    const handleGenerateQueries = async () => {
        setIsProcessing(true);
        setError('');
        setStepData(prev => ({
            ...prev,
            'generate-queries': { ...prev['generate-queries'], status: 'loading' }
        }));

        try {
            const response = await fetch(`${API_BASE_URL}/api/intelligence/voc-discovery/generate-queries`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    segment_name: segmentName,
                    filtered_posts: stepData['analyze-posts'].data,
                    trends: stepData['fetch-trends'].data,
                }),
            });

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            const data = await response.json();
            setStepData(prev => ({
                ...prev,
                'generate-queries': {
                    status: 'completed',
                    data: data.queries || [],
                    duration: data.duration_ms
                }
            }));
        } catch (err) {
            console.error('Query generation failed:', err);
            setError('Failed to generate queries. Please try again.');
            setStepData(prev => ({
                ...prev,
                'generate-queries': { ...prev['generate-queries'], status: 'error', error: err.message }
            }));
        } finally {
            setIsProcessing(false);
        }
    };

    const handleExecuteStep = () => {
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
        }
    };

    const canProceedToStep = (stepIndex) => {
        if (stepIndex === 0) return true;
        const prevStep = STEPS[stepIndex - 1];
        return stepData[prevStep.id].status === 'completed';
    };

    const handleStepClick = (stepIndex) => {
        if (canProceedToStep(stepIndex)) {
            setCurrentStep(stepIndex);
        }
    };

    const handleNext = () => {
        if (currentStep < STEPS.length - 1) {
            setCurrentStep(currentStep + 1);
        }
    };

    const handlePrevious = () => {
        if (currentStep > 0) {
            setCurrentStep(currentStep - 1);
        }
    };

    const handleReset = () => {
        setCurrentStep(0);
        setStepData({
            'fetch-reddit': { status: 'pending', data: null, warnings: [], duration: null },
            'pre-score-posts': { status: 'pending', data: null, duration: null },
            'enrich-posts': { status: 'pending', data: null, duration: null },
            'fetch-trends': { status: 'pending', data: null, duration: null },
            'generate-queries': { status: 'pending', data: null, duration: null },
        });
        setWarnings([]);
        setError('');
    };

    const currentStepId = STEPS[currentStep].id;
    const currentStepInfo = stepData[currentStepId];
    const currentStepDef = STEPS[currentStep];

    return (
        <Box>
            {/* Segment Selector */}
            <Stack direction="row" spacing={2} alignItems="center" mb={3}>
                <TextField
                    select
                    label="Audience Segment"
                    value={segmentName}
                    onChange={(e) => setSegmentName(e.target.value)}
                    sx={{ minWidth: 220 }}
                    size="small"
                    disabled={currentStep > 0}
                >
                    {availableSegments.map((segment) => (
                        <MenuItem key={segment} value={segment}>
                            {segment}
                        </MenuItem>
                    ))}
                </TextField>

                {currentStep > 0 && (
                    <Button
                        variant="outlined"
                        onClick={handleReset}
                        size="small"
                    >
                        Reset
                    </Button>
                )}
            </Stack>

            {/* Horizontal Stepper Layout */}
            <Box sx={{ display: 'flex', minHeight: 600, border: `1px solid ${CustomColors.UIGrey300}`, borderRadius: 2, overflow: 'hidden' }}>
                {/* Left Sidebar - Step Indicator */}
                <Box sx={{ 
                    width: 280, 
                    borderRight: `1px solid ${CustomColors.UIGrey300}`, 
                    bgcolor: CustomColors.UIGrey100,
                    p: 3,
                }}>
                    <Typography variant="body2" color="text.secondary" sx={{ mb: 2, textTransform: 'uppercase', letterSpacing: 0.5, fontSize: 11 }}>
                        VOC Discovery Pipeline
                    </Typography>
                    <List sx={{ p: 0 }}>
                        {STEPS.map((step, index) => {
                            const stepInfo = stepData[step.id];
                            const StepIcon = step.icon;
                            const isActive = index === currentStep;
                            const isCompleted = stepInfo.status === 'completed';
                            const isClickable = canProceedToStep(index);

                            return (
                                <React.Fragment key={step.id}>
                                    <ListItemButton
                                        onClick={() => handleStepClick(index)}
                                        disabled={!isClickable}
                                        selected={isActive}
                                        sx={{
                                            borderRadius: 1,
                                            mb: 0.5,
                                            '&.Mui-selected': {
                                                bgcolor: CustomColors.DeepSkyBlue + '15',
                                                borderLeft: `3px solid ${CustomColors.DeepSkyBlue}`,
                                            },
                                        }}
                                    >
                                        <ListItemIcon sx={{ minWidth: 40 }}>
                                            {isCompleted ? (
                                                <CheckCircleIcon sx={{ color: CustomColors.SecretGarden }} />
                                            ) : stepInfo.status === 'loading' ? (
                                                <CircularProgress size={20} />
                                            ) : (
                                                <StepIcon sx={{ color: isActive ? CustomColors.DeepSkyBlue : CustomColors.UIGrey500 }} />
                                            )}
                                        </ListItemIcon>
                                        <ListItemText
                                            primary={step.label}
                                            secondary={
                                                <Stack spacing={0.5}>
                                                    <Typography variant="caption" color="text.secondary">
                                                        {step.description}
                                                    </Typography>
                                                    {isCompleted && stepInfo.data && (
                                                        <Typography variant="caption" sx={{ color: CustomColors.SecretGarden }}>
                                                            {Array.isArray(stepInfo.data) ? `${stepInfo.data.length} items` : 'Complete'}
                                                        </Typography>
                                                    )}
                                                    {stepInfo.warnings?.length > 0 && (
                                                        <Typography variant="caption" sx={{ color: CustomColors.Pumpkin }}>
                                                            {stepInfo.warnings.length} warning(s)
                                                        </Typography>
                                                    )}
                                                </Stack>
                                            }
                                            primaryTypographyProps={{
                                                fontWeight: isActive ? FontWeight.SemiBold : FontWeight.Medium,
                                                fontSize: 14,
                                            }}
                                        />
                                    </ListItemButton>
                                </React.Fragment>
                            );
                        })}
                    </List>
                </Box>

                {/* Main Content Area */}
                <Box sx={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
                    {/* Header */}
                    <Box sx={{ p: 3, borderBottom: `1px solid ${CustomColors.UIGrey300}` }}>
                        <Typography variant="h5" fontWeight={FontWeight.SemiBold}>
                            {currentStepDef.label}
                        </Typography>
                        <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
                            {currentStepDef.description}
                        </Typography>
                    </Box>

                    {/* Content */}
                    <Box sx={{ flex: 1, p: 3, overflow: 'auto' }}>
                        {/* Config Display for Step 0 */}
                        {currentStep === 0 && segmentConfig && (
                            <Card sx={{ mb: 3 }}>
                                <CardContent>
                                    <Grid container spacing={2}>
                                        <Grid item xs={12} md={6}>
                                            <Typography variant="subtitle2" color="text.secondary" gutterBottom>
                                                Subreddits to Search
                                            </Typography>
                                            {segmentConfig.subreddits?.length ? (
                                                <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
                                                    {segmentConfig.subreddits.map((subreddit) => (
                                                        <Chip key={subreddit} label={`r/${subreddit}`} size="small" />
                                                    ))}
                                                </Stack>
                                            ) : (
                                                <Typography variant="body2" color="text.secondary">
                                                    No subreddits configured
                                                </Typography>
                                            )}
                                        </Grid>
                                        <Grid item xs={12} md={6}>
                                            <Typography variant="subtitle2" color="text.secondary" gutterBottom>
                                                Google Trends Keywords
                                            </Typography>
                                            {segmentConfig.trends_keywords?.length ? (
                                                <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
                                                    {segmentConfig.trends_keywords.map((keyword) => (
                                                        <Chip key={keyword} label={keyword} size="small" />
                                                    ))}
                                                </Stack>
                                            ) : (
                                                <Typography variant="body2" color="text.secondary">
                                                    No keywords configured
                                                </Typography>
                                            )}
                                        </Grid>
                                    </Grid>
                                </CardContent>
                            </Card>
                        )}

                        {/* Error Display */}
                        {error && (
                            <Alert severity="error" sx={{ mb: 2 }}>
                                {error}
                            </Alert>
                        )}

                        {/* Warnings Display */}
                        {currentStepInfo.warnings?.length > 0 && (
                            <Alert severity="warning" icon={<WarningIcon />} sx={{ mb: 2 }}>
                                <Typography variant="body2" fontWeight={FontWeight.SemiBold} gutterBottom>
                                    Warnings:
                                </Typography>
                                {currentStepInfo.warnings.map((warning, idx) => (
                                    <Typography key={idx} variant="body2">
                                        • {warning}
                                    </Typography>
                                ))}
                            </Alert>
                        )}

                        {/* Pending State */}
                        {currentStepInfo.status === 'pending' && (
                            <Box sx={{ textAlign: 'center', py: 8 }}>
                                <Typography variant="body1" color="text.secondary" gutterBottom>
                                    Ready to execute this step
                                </Typography>
                                <Button
                                    variant="contained"
                                    onClick={handleExecuteStep}
                                    disabled={isProcessing}
                                    startIcon={isProcessing ? <CircularProgress size={20} /> : null}
                                    sx={{ mt: 2 }}
                                >
                                    {isProcessing ? 'Processing...' : `Run ${currentStepDef.label}`}
                                </Button>
                            </Box>
                        )}

                        {/* Loading State */}
                        {currentStepInfo.status === 'loading' && (
                            <Box sx={{ textAlign: 'center', py: 8 }}>
                                <CircularProgress size={48} sx={{ mb: 2 }} />
                                <Typography variant="body1" color="text.secondary">
                                    Processing {currentStepDef.label.toLowerCase()}...
                                </Typography>
                            </Box>
                        )}

                        {/* Completed State with Results */}
                        {currentStepInfo.status === 'completed' && (
                            <Box>
                                {currentStepInfo.duration && (
                                    <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                                        Completed in {(currentStepInfo.duration / 1000).toFixed(1)}s
                                    </Typography>
                                )}

                                {/* Results for Fetch Reddit */}
                                {currentStepId === 'fetch-reddit' && currentStepInfo.data && (
                                    <Box>
                                        {/* Filtered Posts Section */}
                                        <Typography variant="h6" fontWeight={FontWeight.Medium} gutterBottom>
                                            Filtered Posts ({currentStepInfo.data.length} posts passed filters)
                                        </Typography>
                                        <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                                            Posts that passed score ≥ 20 and comments ≥ 10 thresholds
                                        </Typography>
                                        {(() => {
                                            // Group filtered posts by subreddit
                                            const postsBySubreddit = currentStepInfo.data.reduce((acc, post) => {
                                                const subreddit = post.subreddit || 'unknown';
                                                if (!acc[subreddit]) {
                                                    acc[subreddit] = [];
                                                }
                                                acc[subreddit].push(post);
                                                return acc;
                                            }, {});

                                            return Object.entries(postsBySubreddit).map(([subreddit, posts]) => (
                                                <Accordion key={subreddit} sx={{ mb: 1 }}>
                                                    <AccordionSummary expandIcon={<ExpandMoreIcon />}>
                                                        <Stack direction="row" spacing={2} alignItems="center">
                                                            <Typography fontWeight={FontWeight.SemiBold}>
                                                                r/{subreddit}
                                                            </Typography>
                                                            <Chip 
                                                                label={`${posts.length} posts`} 
                                                                size="small" 
                                                                sx={{ bgcolor: CustomColors.SecretGarden + '20' }}
                                                            />
                                                        </Stack>
                                                    </AccordionSummary>
                                                    <AccordionDetails>
                                                        <TableContainer>
                                                            <Table size="small">
                                                                <TableHead>
                                                                    <TableRow>
                                                                        <TableCell sx={{ fontWeight: FontWeight.SemiBold }}>Title</TableCell>
                                                                        <TableCell align="right" sx={{ fontWeight: FontWeight.SemiBold }}>Score</TableCell>
                                                                        <TableCell align="right" sx={{ fontWeight: FontWeight.SemiBold }}>Comments</TableCell>
                                                                        <TableCell align="right" sx={{ fontWeight: FontWeight.SemiBold }}>Posted</TableCell>
                                                                        <TableCell sx={{ fontWeight: FontWeight.SemiBold }}>Link</TableCell>
                                                                    </TableRow>
                                                                </TableHead>
                                                                <TableBody>
                                                                    {posts.map((post) => (
                                                                        <TableRow key={post.id} hover>
                                                                            <TableCell sx={{ maxWidth: 400 }}>
                                                                                <Typography 
                                                                                    variant="body2" 
                                                                                    sx={{ 
                                                                                        overflow: 'hidden',
                                                                                        textOverflow: 'ellipsis',
                                                                                        whiteSpace: 'nowrap'
                                                                                    }}
                                                                                    title={post.title}
                                                                                >
                                                                                    {post.title}
                                                                                </Typography>
                                                                            </TableCell>
                                                                            <TableCell align="right">
                                                                                <Typography variant="body2">
                                                                                    {post.score?.toLocaleString() || 0}
                                                                                </Typography>
                                                                            </TableCell>
                                                                            <TableCell align="right">
                                                                                <Typography variant="body2">
                                                                                    {post.num_comments?.toLocaleString() || 0}
                                                                                </Typography>
                                                                            </TableCell>
                                                                            <TableCell align="right">
                                                                                <Typography variant="body2" sx={{ whiteSpace: 'nowrap' }}>
                                                                                    {post.created_utc ? new Date(post.created_utc * 1000).toLocaleDateString() : 'N/A'}
                                                                                </Typography>
                                                                            </TableCell>
                                                                            <TableCell>
                                                                                {post.permalink ? (
                                                                                    <Link 
                                                                                        href={`https://reddit.com${post.permalink}`}
                                                                                        target="_blank"
                                                                                        rel="noreferrer"
                                                                                        variant="body2"
                                                                                    >
                                                                                        Reddit
                                                                                    </Link>
                                                                                ) : post.url ? (
                                                                                    <Link 
                                                                                        href={post.url}
                                                                                        target="_blank"
                                                                                        rel="noreferrer"
                                                                                        variant="body2"
                                                                                    >
                                                                                        Link
                                                                                    </Link>
                                                                                ) : (
                                                                                    <Typography variant="body2" color="text.secondary">
                                                                                        No link
                                                                                    </Typography>
                                                                                )}
                                                                            </TableCell>
                                                                        </TableRow>
                                                                    ))}
                                                                </TableBody>
                                                            </Table>
                                                        </TableContainer>
                                                    </AccordionDetails>
                                                </Accordion>
                                            ));
                                        })()}

                                        <Divider sx={{ my: 4 }} />

                                        {/* Raw Data View - Grouped by Subreddit */}
                                        <Box sx={{ mt: 4 }}>
                                            <Typography variant="h6" fontWeight={FontWeight.Medium} gutterBottom>
                                                Raw Unfiltered Data ({currentStepInfo.unfilteredData?.length || 0} total posts)
                                            </Typography>
                                            <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                                                ALL posts returned from the API before any score/comment filtering
                                            </Typography>
                                            {(() => {
                                                // Group posts by subreddit using unfiltered data
                                                const postsToShow = currentStepInfo.unfilteredData || currentStepInfo.data;
                                                const postsBySubreddit = postsToShow.reduce((acc, post) => {
                                                    const subreddit = post.subreddit || 'unknown';
                                                    if (!acc[subreddit]) {
                                                        acc[subreddit] = [];
                                                    }
                                                    acc[subreddit].push(post);
                                                    return acc;
                                                }, {});

                                                return Object.entries(postsBySubreddit).map(([subreddit, posts]) => (
                                                    <Accordion key={subreddit} sx={{ mb: 1 }}>
                                                        <AccordionSummary expandIcon={<ExpandMoreIcon />}>
                                                            <Stack direction="row" spacing={2} alignItems="center">
                                                                <Typography fontWeight={FontWeight.SemiBold}>
                                                                    r/{subreddit}
                                                                </Typography>
                                                                <Chip 
                                                                    label={`${posts.length} posts`} 
                                                                    size="small" 
                                                                    sx={{ bgcolor: CustomColors.UIGrey400 }}
                                                                />
                                                            </Stack>
                                                        </AccordionSummary>
                                                        <AccordionDetails>
                                                            <TableContainer>
                                                                <Table size="small">
                                                                    <TableHead>
                                                                        <TableRow>
                                                                            <TableCell sx={{ fontWeight: FontWeight.SemiBold }}>Title</TableCell>
                                                                            <TableCell align="right" sx={{ fontWeight: FontWeight.SemiBold }}>Score</TableCell>
                                                                            <TableCell align="right" sx={{ fontWeight: FontWeight.SemiBold }}>Comments</TableCell>
                                                                            <TableCell align="right" sx={{ fontWeight: FontWeight.SemiBold }}>Posted</TableCell>
                                                                            <TableCell sx={{ fontWeight: FontWeight.SemiBold }}>Link</TableCell>
                                                                        </TableRow>
                                                                    </TableHead>
                                                                    <TableBody>
                                                                        {posts.map((post) => (
                                                                            <TableRow key={post.id} hover>
                                                                                <TableCell sx={{ maxWidth: 400 }}>
                                                                                    <Typography 
                                                                                        variant="body2" 
                                                                                        sx={{ 
                                                                                            overflow: 'hidden',
                                                                                            textOverflow: 'ellipsis',
                                                                                            whiteSpace: 'nowrap'
                                                                                        }}
                                                                                        title={post.title}
                                                                                    >
                                                                                        {post.title}
                                                                                    </Typography>
                                                                                </TableCell>
                                                                                <TableCell align="right">
                                                                                    <Typography variant="body2">
                                                                                        {post.score?.toLocaleString() || 0}
                                                                                    </Typography>
                                                                                </TableCell>
                                                                                <TableCell align="right">
                                                                                    <Typography variant="body2">
                                                                                        {post.num_comments?.toLocaleString() || 0}
                                                                                    </Typography>
                                                                                </TableCell>
                                                                                <TableCell align="right">
                                                                                    <Typography variant="body2" sx={{ whiteSpace: 'nowrap' }}>
                                                                                        {post.created_utc ? new Date(post.created_utc * 1000).toLocaleDateString() : 'N/A'}
                                                                                    </Typography>
                                                                                </TableCell>
                                                                                <TableCell>
                                                                                    {post.permalink ? (
                                                                                        <Link 
                                                                                            href={`https://reddit.com${post.permalink}`}
                                                                                            target="_blank"
                                                                                            rel="noreferrer"
                                                                                            variant="body2"
                                                                                        >
                                                                                            Reddit
                                                                                        </Link>
                                                                                    ) : post.url ? (
                                                                                        <Link 
                                                                                            href={post.url}
                                                                                            target="_blank"
                                                                                            rel="noreferrer"
                                                                                            variant="body2"
                                                                                        >
                                                                                            Link
                                                                                        </Link>
                                                                                    ) : (
                                                                                        <Typography variant="body2" color="text.secondary">
                                                                                            No link
                                                                                        </Typography>
                                                                                    )}
                                                                                </TableCell>
                                                                            </TableRow>
                                                                        ))}
                                                                    </TableBody>
                                                                </Table>
                                                            </TableContainer>
                                                        </AccordionDetails>
                                                    </Accordion>
                                                ));
                                            })()}
                                        </Box>
                                    </Box>
                                )}

                                {/* Results for Pre-Score Posts */}
                                {currentStepId === 'pre-score-posts' && currentStepInfo.data && (
                                    <Box>
                                        <Typography variant="h6" fontWeight={FontWeight.Medium} gutterBottom>
                                            Pre-Score Results
                                        </Typography>
                                        
                                        {/* Stats Summary */}
                                        {currentStepInfo.stats && (
                                            <Stack direction="row" spacing={2} sx={{ mb: 3 }}>
                                                <Chip 
                                                    label={`${currentStepInfo.stats.input} Input Posts`} 
                                                    sx={{ bgcolor: CustomColors.UIGrey400 }}
                                                />
                                                <Chip 
                                                    label={`${currentStepInfo.stats.promising} Passed (≥${currentStepInfo.threshold})`} 
                                                    sx={{ bgcolor: CustomColors.SecretGarden + '20' }}
                                                />
                                                <Chip 
                                                    label={`${currentStepInfo.stats.rejected} Rejected`} 
                                                    sx={{ bgcolor: CustomColors.UIGrey300 }}
                                                />
                                            </Stack>
                                        )}

                                        {/* Promising Posts (Passed Threshold) */}
                                        <Typography variant="subtitle1" fontWeight={FontWeight.SemiBold} gutterBottom>
                                            High-Scoring Posts ({currentStepInfo.data.length})
                                        </Typography>
                                        <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                                            These posts scored ≥{currentStepInfo.threshold} and will move to enrichment
                                        </Typography>
                                        {(() => {
                                            const postsBySubreddit = currentStepInfo.data.reduce((acc, post) => {
                                                const subreddit = post.subreddit || 'unknown';
                                                if (!acc[subreddit]) acc[subreddit] = [];
                                                acc[subreddit].push(post);
                                                return acc;
                                            }, {});

                                            return Object.entries(postsBySubreddit).map(([subreddit, posts]) => (
                                                <Accordion key={subreddit} sx={{ mb: 1 }}>
                                                    <AccordionSummary expandIcon={<ExpandMoreIcon />}>
                                                        <Stack direction="row" spacing={2} alignItems="center">
                                                            <Typography fontWeight={FontWeight.SemiBold}>
                                                                r/{subreddit}
                                                            </Typography>
                                                            <Chip 
                                                                label={`${posts.length} posts`} 
                                                                size="small" 
                                                                sx={{ bgcolor: CustomColors.SecretGarden + '20' }}
                                                            />
                                                        </Stack>
                                                    </AccordionSummary>
                                                    <AccordionDetails>
                                                        <TableContainer>
                                                            <Table size="small">
                                                                <TableHead>
                                                                    <TableRow>
                                                                        <TableCell sx={{ fontWeight: FontWeight.SemiBold }}>Title</TableCell>
                                                                        <TableCell align="right" sx={{ fontWeight: FontWeight.SemiBold }}>Score</TableCell>
                                                                        <TableCell align="right" sx={{ fontWeight: FontWeight.SemiBold }}>AI Score</TableCell>
                                                                        <TableCell sx={{ fontWeight: FontWeight.SemiBold }}>Reason</TableCell>
                                                                        <TableCell sx={{ fontWeight: FontWeight.SemiBold }}>Link</TableCell>
                                                                    </TableRow>
                                                                </TableHead>
                                                                <TableBody>
                                                                    {posts.map((post) => (
                                                                        <TableRow key={post.id} hover>
                                                                            <TableCell sx={{ maxWidth: 300 }}>
                                                                                <Typography 
                                                                                    variant="body2" 
                                                                                    sx={{ 
                                                                                        overflow: 'hidden',
                                                                                        textOverflow: 'ellipsis',
                                                                                        whiteSpace: 'nowrap'
                                                                                    }}
                                                                                    title={post.title}
                                                                                >
                                                                                    {post.title}
                                                                                </Typography>
                                                                            </TableCell>
                                                                            <TableCell align="right">
                                                                                <Typography variant="body2">
                                                                                    {post.score?.toLocaleString() || 0}
                                                                                </Typography>
                                                                            </TableCell>
                                                                            <TableCell align="right">
                                                                                <Chip 
                                                                                    label={post.prescore?.relevance_score?.toFixed(1) || 'N/A'}
                                                                                    size="small"
                                                                                    sx={{ 
                                                                                        bgcolor: post.prescore?.relevance_score >= currentStepInfo.threshold 
                                                                                            ? CustomColors.SecretGarden + '40' 
                                                                                            : CustomColors.UIGrey300 
                                                                                    }}
                                                                                />
                                                                            </TableCell>
                                                                            <TableCell sx={{ maxWidth: 300 }}>
                                                                                <Typography 
                                                                                    variant="body2" 
                                                                                    sx={{ 
                                                                                        overflow: 'hidden',
                                                                                        textOverflow: 'ellipsis',
                                                                                        whiteSpace: 'nowrap'
                                                                                    }}
                                                                                    title={post.prescore?.quick_reason}
                                                                                >
                                                                                    {post.prescore?.quick_reason || 'No reason provided'}
                                                                                </Typography>
                                                                            </TableCell>
                                                                            <TableCell>
                                                                                {post.permalink ? (
                                                                                    <Link 
                                                                                        href={`https://reddit.com${post.permalink}`}
                                                                                        target="_blank"
                                                                                        rel="noreferrer"
                                                                                        variant="body2"
                                                                                    >
                                                                                        Reddit
                                                                                    </Link>
                                                                                ) : (
                                                                                    <Typography variant="body2" color="text.secondary">
                                                                                        No link
                                                                                    </Typography>
                                                                                )}
                                                                            </TableCell>
                                                                        </TableRow>
                                                                    ))}
                                                                </TableBody>
                                                            </Table>
                                                        </TableContainer>
                                                    </AccordionDetails>
                                                </Accordion>
                                            ));
                                        })()}
                                    </Box>
                                )}

                                {/* Results for Enrich Posts */}
                                {currentStepId === 'enrich-posts' && currentStepInfo.data && (
                                    <Box>
                                        <Typography variant="h6" fontWeight={FontWeight.Medium} gutterBottom>
                                            Enriched Posts with Deep Analysis
                                        </Typography>
                                        
                                        {/* Stats Summary */}
                                        {currentStepInfo.stats && (
                                            <Stack direction="row" spacing={2} sx={{ mb: 3 }}>
                                                <Chip 
                                                    label={`${currentStepInfo.stats.input} Input Posts`} 
                                                    sx={{ bgcolor: CustomColors.UIGrey400 }}
                                                />
                                                <Chip 
                                                    label={`${currentStepInfo.stats.final_accepted} Final Accepted (≥${currentStepInfo.threshold})`} 
                                                    sx={{ bgcolor: CustomColors.SecretGarden + '20' }}
                                                />
                                                <Chip 
                                                    label={`${currentStepInfo.stats.final_rejected} Rejected`} 
                                                    sx={{ bgcolor: CustomColors.UIGrey300 }}
                                                />
                                            </Stack>
                                        )}

                                        <Box sx={{ maxHeight: 600, overflow: 'auto' }}>
                                            {currentStepInfo.data.map((post) => (
                                                <PostCard key={post.id} post={post} showAnalysis={true} />
                                            ))}
                                        </Box>
                                    </Box>
                                )}

                                {/* Results for Analyze Posts */}
                                {currentStepId === 'analyze-posts' && currentStepInfo.data && (
                                    <Box>
                                        <Typography variant="h6" fontWeight={FontWeight.Medium} gutterBottom>
                                            AI Analysis ({currentStepInfo.data.length} posts passed filters)
                                        </Typography>
                                        <Box sx={{ maxHeight: 400, overflow: 'auto' }}>
                                            {currentStepInfo.data.slice(0, 5).map((post) => (
                                                <PostCard key={post.id} post={post} showAnalysis={true} />
                                            ))}
                                            {currentStepInfo.data.length > 5 && (
                                                <Typography variant="body2" color="text.secondary" sx={{ textAlign: 'center', pt: 2 }}>
                                                    ...and {currentStepInfo.data.length - 5} more
                                                </Typography>
                                            )}
                                        </Box>
                                    </Box>
                                )}

                                {/* Results for Fetch Trends */}
                                {currentStepId === 'fetch-trends' && currentStepInfo.data && (
                                    <Box>
                                        <Typography variant="h6" fontWeight={FontWeight.Medium} gutterBottom>
                                            Google Trends ({currentStepInfo.data.length} keywords)
                                        </Typography>
                                        <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap sx={{ mt: 2 }}>
                                            {currentStepInfo.data.map((trend) => (
                                                <Chip key={trend.keyword} label={trend.keyword} />
                                            ))}
                                        </Stack>
                                    </Box>
                                )}

                                {/* Results for Generate Queries */}
                                {currentStepId === 'generate-queries' && currentStepInfo.data && (
                                    <Box>
                                        <Typography variant="h6" fontWeight={FontWeight.Medium} gutterBottom>
                                            Curated Research Prompts ({currentStepInfo.data.length})
                                        </Typography>
                                        <Stack spacing={1} sx={{ mt: 2 }}>
                                            {currentStepInfo.data.map((query, idx) => (
                                                <Typography key={idx} variant="body2">
                                                    • {query}
                                                </Typography>
                                            ))}
                                        </Stack>
                                    </Box>
                                )}
                            </Box>
                        )}

                        {/* Error State */}
                        {currentStepInfo.status === 'error' && (
                            <Box sx={{ textAlign: 'center', py: 8 }}>
                                <WarningIcon sx={{ fontSize: 48, color: 'error.main', mb: 2 }} />
                                <Typography variant="h6" color="error" gutterBottom>
                                    Error
                                </Typography>
                                <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                                    {currentStepInfo.error}
                                </Typography>
                                <Button
                                    variant="contained"
                                    color="error"
                                    onClick={handleExecuteStep}
                                >
                                    Retry
                                </Button>
                            </Box>
                        )}
                    </Box>

                    {/* Footer Navigation */}
                    <Box sx={{ 
                        p: 2, 
                        borderTop: `1px solid ${CustomColors.UIGrey300}`,
                        display: 'flex',
                        justifyContent: 'space-between',
                        alignItems: 'center',
                    }}>
                        <Button
                            onClick={handlePrevious}
                            disabled={currentStep === 0 || isProcessing}
                            startIcon={<ChevronLeftIcon />}
                        >
                            Previous
                        </Button>

                        {currentStep < STEPS.length - 1 && (
                            <Button
                                variant="contained"
                                onClick={handleNext}
                                disabled={currentStepInfo.status !== 'completed' || isProcessing}
                                endIcon={<ChevronRightIcon />}
                            >
                                Next Step
                            </Button>
                        )}
                    </Box>
                </Box>
            </Box>
        </Box>
    );
};

export default VOCDiscovery;