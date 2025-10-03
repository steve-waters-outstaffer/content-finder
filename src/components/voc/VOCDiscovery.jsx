import React from 'react';
import { Box, Button, MenuItem, Stack, TextField } from '@mui/material';
import { CustomColors } from '../../theme';
import { STEPS } from './constants';
import VOCStepIndicator from './VOCStepIndicator';
import VOCStepContent from './VOCStepContent';
import { useVOCDiscovery } from './useVOCDiscovery';

const VOCDiscovery = () => {
    const {
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
    } = useVOCDiscovery();

    const isFirstStep = currentStep === 0;
    const isLastStep = currentStep === STEPS.length - 1;

    return (
        <Box>
            <Stack direction="row" spacing={2} alignItems="center" mb={3}>
                <TextField
                    select
                    label="Audience Segment"
                    value={segmentName}
                    onChange={(event) => setSegmentName(event.target.value)}
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
                    <Button variant="outlined" onClick={handleReset} size="small">
                        Reset
                    </Button>
                )}
            </Stack>

            <Box
                sx={{
                    display: 'flex',
                    minHeight: 600,
                    border: `1px solid ${CustomColors.UIGrey300}`,
                    borderRadius: 2,
                    overflow: 'hidden',
                }}
            >
                <VOCStepIndicator
                    steps={STEPS}
                    currentStep={currentStep}
                    stepData={stepData}
                    canProceedToStep={canProceedToStep}
                    onStepClick={handleStepClick}
                />
                <VOCStepContent
                    step={currentStepDef}
                    stepInfo={currentStepInfo}
                    error={error}
                    isProcessing={isProcessing}
                    onExecute={handleExecuteStep}
                    onNext={handleNext}
                    onPrevious={handlePrevious}
                    canProceed={currentStepInfo?.status === 'completed'}
                    isFirstStep={isFirstStep}
                    isLastStep={isLastStep}
                    segmentConfig={segmentConfig}
                />
            </Box>
        </Box>
    );
};

export default VOCDiscovery;
