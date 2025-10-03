import React from 'react';
import {
    Alert,
    Box,
    Button,
    Card,
    CardContent,
    Chip,
    CircularProgress,
    Grid,
    Stack,
    Typography,
} from '@mui/material';
import WarningIcon from '@mui/icons-material/Warning';
import ChevronLeftIcon from '@mui/icons-material/ChevronLeft';
import ChevronRightIcon from '@mui/icons-material/ChevronRight';
import { CustomColors, FontWeight } from '../../theme';
import FetchRedditResults from './results/FetchRedditResults';
import PreScoreResults from './results/PreScoreResults';
import EnrichPostsResults from './results/EnrichPostsResults';
import FetchTrendsResults from './results/FetchTrendsResults';
import GenerateQueriesResults from './results/GenerateQueriesResults';

const resultsMap = {
    'fetch-reddit': FetchRedditResults,
    'pre-score-posts': PreScoreResults,
    'enrich-posts': EnrichPostsResults,
    'fetch-trends': FetchTrendsResults,
    'generate-queries': GenerateQueriesResults,
};

const VOCStepContent = ({
    step,
    stepInfo,
    error,
    isProcessing,
    onExecute,
    onNext,
    onPrevious,
    canProceed,
    isFirstStep,
    isLastStep,
    segmentConfig,
}) => {
    const ResultComponent = resultsMap[step.id];
    const status = stepInfo?.status ?? 'pending';

    return (
        <Box sx={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
            <Box sx={{ flex: 1, p: 3, bgcolor: 'background.paper' }}>
                <Stack spacing={1} sx={{ mb: 3 }}>
                    <Typography variant="h5" fontWeight={FontWeight.SemiBold}>
                        {step.label}
                    </Typography>
                    <Typography variant="body2" color="text.secondary">
                        {step.description}
                    </Typography>
                </Stack>

                {step.id === 'fetch-reddit' && segmentConfig && (
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

                {error && (
                    <Alert severity="error" sx={{ mb: 2 }}>
                        {error}
                    </Alert>
                )}

                {stepInfo?.warnings?.length > 0 && (
                    <Alert severity="warning" icon={<WarningIcon />} sx={{ mb: 2 }}>
                        <Typography variant="body2" fontWeight={FontWeight.SemiBold} gutterBottom>
                            Warnings:
                        </Typography>
                        {stepInfo.warnings.map((warning, idx) => (
                            <Typography key={idx} variant="body2">
                                • {warning}
                            </Typography>
                        ))}
                    </Alert>
                )}

                {status === 'pending' && (
                    <Box sx={{ textAlign: 'center', py: 8 }}>
                        <Typography variant="body1" color="text.secondary" gutterBottom>
                            Ready to execute this step
                        </Typography>
                        <Button
                            variant="contained"
                            onClick={onExecute}
                            disabled={isProcessing}
                            startIcon={isProcessing ? <CircularProgress size={20} /> : null}
                            sx={{ mt: 2 }}
                        >
                            {isProcessing ? 'Processing...' : `Run ${step.label}`}
                        </Button>
                    </Box>
                )}

                {status === 'loading' && (
                    <Box sx={{ textAlign: 'center', py: 8 }}>
                        <CircularProgress size={48} sx={{ mb: 2 }} />
                        <Typography variant="body1" color="text.secondary">
                            Processing {step.label.toLowerCase()}...
                        </Typography>
                    </Box>
                )}

                {status === 'completed' && (
                    <Box>
                        {stepInfo?.duration && (
                            <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                                Completed in {(stepInfo.duration / 1000).toFixed(1)}s
                            </Typography>
                        )}
                        {ResultComponent && <ResultComponent stepInfo={stepInfo} />}
                    </Box>
                )}

                {status === 'error' && (
                    <Box sx={{ textAlign: 'center', py: 8 }}>
                        <WarningIcon sx={{ fontSize: 48, color: 'error.main', mb: 2 }} />
                        <Typography variant="h6" color="error" gutterBottom>
                            Error
                        </Typography>
                        <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                            {stepInfo?.error}
                        </Typography>
                        <Button variant="contained" color="error" onClick={onExecute}>
                            Retry
                        </Button>
                    </Box>
                )}
            </Box>

            <Box
                sx={{
                    p: 2,
                    borderTop: `1px solid ${CustomColors.UIGrey300}`,
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                }}
            >
                <Button onClick={onPrevious} disabled={isFirstStep || isProcessing} startIcon={<ChevronLeftIcon />}>
                    Previous
                </Button>

                {!isLastStep && (
                    <Button
                        variant="contained"
                        onClick={onNext}
                        disabled={!canProceed || isProcessing}
                        endIcon={<ChevronRightIcon />}
                    >
                        Next Step
                    </Button>
                )}
            </Box>
        </Box>
    );
};

export default VOCStepContent;
